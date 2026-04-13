import { SovereignVault } from "./sovereign_vault_mcp";
import {
  runSovereignLoop,
  CustomerRecord,
  WorkflowStage,
} from "./sovereign_recursive_loop_v2";
import * as fs from "fs/promises";
import * as assert from "assert";

const TEST_VAULT_PATH = "/tmp/test_vault.json";

async function cleanup() {
  try {
    await fs.unlink(TEST_VAULT_PATH);
  } catch {
    // ignore
  }
}

function makeCustomer(
  overrides: Partial<CustomerRecord> = {}
): CustomerRecord {
  return {
    id: "test_001",
    name: "Test Customer",
    email: "test@example.com",
    phone: "555-0199",
    address: "456 Test Ave, Phoenix AZ 85001",
    stage: "lead",
    notes: ["Monthly bill: $200"],
    lastContact: new Date().toISOString(),
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

async function testVaultPersistence() {
  console.log("\n[Test 1] Vault persistence...");
  const vault = new SovereignVault(TEST_VAULT_PATH);
  await vault.init();

  const customer = makeCustomer();
  await vault.saveCustomer(customer);

  const retrieved = await vault.getCustomer("test_001");
  assert.ok(retrieved, "Customer should be retrievable");
  assert.strictEqual(retrieved!.name, "Test Customer");

  await vault.appendMessage("test_001", "user", "Hello");
  await vault.appendMessage("test_001", "assistant", "Hi there!");
  const history = await vault.getCustomerHistory("test_001");
  assert.strictEqual(history.length, 2);

  console.log("  PASS: Vault persistence");
}

async function testVaultSearch() {
  console.log("\n[Test 2] Vault search...");
  const vault = new SovereignVault(TEST_VAULT_PATH);
  await vault.init();

  await vault.saveCustomer(makeCustomer({ id: "s1", name: "Alice Solar", email: "alice@example.com" }));
  await vault.saveCustomer(makeCustomer({ id: "s2", name: "Bob Power", email: "bob@example.com" }));

  const results = await vault.searchCustomers("alice");
  assert.strictEqual(results.length, 1);
  assert.strictEqual(results[0].name, "Alice Solar");

  console.log("  PASS: Vault search");
}

async function testVaultStats() {
  console.log("\n[Test 3] Vault stats...");
  const vault = new SovereignVault(TEST_VAULT_PATH);
  await vault.init();

  await vault.saveCustomer(makeCustomer({ id: "st1", stage: "lead" }));
  await vault.saveCustomer(makeCustomer({ id: "st2", stage: "proposal" }));
  await vault.saveCustomer(makeCustomer({ id: "st3", stage: "proposal" }));

  const stats = vault.getStats();
  assert.ok(stats.total >= 2);
  assert.ok(stats.byStage["proposal"] >= 2);

  console.log("  PASS: Vault stats");
}

async function testStageByStageFilter() {
  console.log("\n[Test 4] Stage filtering...");
  const vault = new SovereignVault(TEST_VAULT_PATH);
  await vault.init();

  await vault.saveCustomer(makeCustomer({ id: "f1", stage: "qualified" }));
  await vault.saveCustomer(makeCustomer({ id: "f2", stage: "lead" }));

  const qualified = await vault.getCustomersByStage("qualified");
  assert.ok(qualified.length >= 1);
  assert.ok(qualified.every((c) => c.stage === "qualified"));

  console.log("  PASS: Stage filtering");
}

async function testFullLoop() {
  console.log("\n[Test 5] Full sovereign loop (live API call)...");
  if (!process.env.ANTHROPIC_API_KEY) {
    console.log("  SKIP: ANTHROPIC_API_KEY not set");
    return;
  }

  const vault = new SovereignVault(TEST_VAULT_PATH);
  await vault.init();

  const customer = makeCustomer({ id: "loop_001" });
  const result = await runSovereignLoop(
    customer,
    "Hi, I'm interested in solar. My electricity bill is $250/month.",
    vault
  );

  assert.ok(result.response.length > 0, "Should have a response");
  assert.ok(result.nextAction.length > 0, "Should have a next action");
  assert.ok(result.updatedRecord.lastContact, "Should update last contact");

  console.log("  PASS: Full loop");
  console.log(`  Stage: ${result.stage}`);
  console.log(`  Next Action: ${result.nextAction}`);
}

(async () => {
  console.log("=== SOVEREIGN LOOP TEST SUITE ===");
  await cleanup();

  try {
    await testVaultPersistence();
    await testVaultSearch();
    await testVaultStats();
    await testStageByStageFilter();
    await testFullLoop();

    console.log("\n=== ALL TESTS PASSED ===");
  } catch (err) {
    console.error("\n=== TEST FAILED ===", err);
    process.exit(1);
  } finally {
    await cleanup();
  }
})();
