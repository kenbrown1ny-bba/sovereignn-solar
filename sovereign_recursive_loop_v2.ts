import Anthropic from "@anthropic-ai/sdk";
import { SovereignVault } from "./sovereign_vault_mcp";

const client = new Anthropic();

export type WorkflowStage =
  | "lead"
  | "qualified"
  | "site_assessment"
  | "proposal"
  | "negotiation"
  | "closed_won"
  | "closed_lost";

export interface CustomerRecord {
  id: string;
  name: string;
  email: string;
  phone?: string;
  address?: string;
  stage: WorkflowStage;
  notes: string[];
  systemSizeKw?: number;
  estimatedSavings?: number;
  proposalUrl?: string;
  lastContact: string;
  createdAt: string;
}

export interface LoopResult {
  customerId: string;
  stage: WorkflowStage;
  response: string;
  nextAction: string;
  updatedRecord: CustomerRecord;
}

const STAGE_PROMPTS: Record<WorkflowStage, string> = {
  lead:
    "You are a friendly solar consultant making first contact. Qualify the lead by asking about their electricity bill, home ownership, and interest in solar savings.",
  qualified:
    "The customer is qualified. Schedule a site assessment and explain the process. Emphasize zero-cost assessment and potential savings.",
  site_assessment:
    "Site assessment is scheduled or completed. Follow up on results, discuss roof condition, shading, and optimal system size.",
  proposal:
    "Present the solar proposal. Walk through system size, cost, financing options, ROI timeline, and incentives like the 30% federal tax credit.",
  negotiation:
    "Customer is reviewing the proposal. Address objections, offer financing alternatives, and emphasize long-term savings and energy independence.",
  closed_won:
    "Sale is closed! Congratulate the customer, outline next steps for installation, timeline, and what to expect during the process.",
  closed_lost:
    "The customer declined. Thank them for their time, leave the door open for future conversations, and ask for referrals.",
};

const NEXT_ACTIONS: Record<WorkflowStage, string> = {
  lead: "Schedule qualification call within 24 hours",
  qualified: "Book site assessment within 3 business days",
  site_assessment: "Prepare custom proposal within 5 business days",
  proposal: "Follow up within 48 hours for questions",
  negotiation: "Schedule decision call within 72 hours",
  closed_won: "Send installation welcome packet and schedule kickoff",
  closed_lost: "Add to nurture campaign and request referrals",
};

export async function runSovereignLoop(
  customer: CustomerRecord,
  incomingMessage: string,
  vault: SovereignVault
): Promise<LoopResult> {
  // Load full customer history from vault
  const history = await vault.getCustomerHistory(customer.id);
  const systemPrompt = STAGE_PROMPTS[customer.stage];

  // Build conversation context with prompt caching for large histories
  const messages: Anthropic.MessageParam[] = [
    ...history.slice(0, -1),
    { role: "user", content: incomingMessage },
  ];

  const response = await client.messages.create({
    model: "claude-opus-4-6",
    max_tokens: 1024,
    system: [
      {
        type: "text",
        text: `${systemPrompt}\n\nCustomer Profile:\nName: ${customer.name}\nStage: ${customer.stage}\nNotes: ${customer.notes.join("; ")}\nLast Contact: ${customer.lastContact}`,
        cache_control: { type: "ephemeral" },
      },
    ],
    messages,
  });

  const assistantMessage =
    response.content[0].type === "text" ? response.content[0].text : "";

  // Determine if stage should advance
  const updatedStage = await evaluateStageTransition(
    customer.stage,
    incomingMessage,
    assistantMessage
  );

  // Update customer record
  const updatedRecord: CustomerRecord = {
    ...customer,
    stage: updatedStage,
    lastContact: new Date().toISOString(),
    notes: [
      ...customer.notes,
      `[${new Date().toLocaleDateString()}] ${incomingMessage.slice(0, 100)}`,
    ],
  };

  // Persist to vault
  await vault.saveCustomer(updatedRecord);
  await vault.appendMessage(customer.id, "user", incomingMessage);
  await vault.appendMessage(customer.id, "assistant", assistantMessage);

  return {
    customerId: customer.id,
    stage: updatedStage,
    response: assistantMessage,
    nextAction: NEXT_ACTIONS[updatedStage],
    updatedRecord,
  };
}

async function evaluateStageTransition(
  currentStage: WorkflowStage,
  userMessage: string,
  assistantResponse: string
): Promise<WorkflowStage> {
  const transitionKeywords: Partial<Record<WorkflowStage, string[]>> = {
    lead: ["interested", "tell me more", "how much", "savings"],
    qualified: ["schedule", "assessment", "visit", "come out"],
    site_assessment: ["proposal", "quote", "price", "cost"],
    proposal: ["think about", "compare", "financing", "payment"],
    negotiation: ["sign", "move forward", "let's do it", "agreed"],
  };

  const stageOrder: WorkflowStage[] = [
    "lead",
    "qualified",
    "site_assessment",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
  ];

  const keywords = transitionKeywords[currentStage] || [];
  const combined = (userMessage + " " + assistantResponse).toLowerCase();
  const shouldAdvance = keywords.some((kw) => combined.includes(kw));

  if (shouldAdvance) {
    const currentIndex = stageOrder.indexOf(currentStage);
    if (currentIndex < stageOrder.length - 2) {
      return stageOrder[currentIndex + 1];
    }
  }

  if (combined.includes("not interested") || combined.includes("no thank")) {
    return "closed_lost";
  }

  return currentStage;
}

// CLI runner for testing
if (require.main === module) {
  (async () => {
    const vault = new SovereignVault("./data/vault.json");
    await vault.init();

    const testCustomer: CustomerRecord = {
      id: "cust_001",
      name: "Jane Smith",
      email: "jane@example.com",
      phone: "555-0100",
      address: "123 Sunny Lane, Phoenix AZ 85001",
      stage: "lead",
      notes: ["Monthly electric bill: $280", "Homeowner, south-facing roof"],
      lastContact: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    };

    const result = await runSovereignLoop(
      testCustomer,
      "Hi, I saw your ad about solar savings. I pay about $280 a month for electricity.",
      vault
    );

    console.log("\n=== SOVEREIGN LOOP RESULT ===");
    console.log(`Customer: ${result.updatedRecord.name}`);
    console.log(`Stage: ${result.stage}`);
    console.log(`Response:\n${result.response}`);
    console.log(`Next Action: ${result.nextAction}`);
  })();
}
