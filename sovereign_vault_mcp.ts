import * as fs from "fs/promises";
import * as path from "path";
import type { CustomerRecord } from "./sovereign_recursive_loop_v2";
import Anthropic from "@anthropic-ai/sdk";

export interface VaultData {
  customers: Record<string, CustomerRecord>;
  conversations: Record<string, Anthropic.MessageParam[]>;
  metadata: {
    version: string;
    lastUpdated: string;
    totalCustomers: number;
  };
}

export class SovereignVault {
  private vaultPath: string;
  private data: VaultData;

  constructor(vaultPath: string) {
    this.vaultPath = path.resolve(vaultPath);
    this.data = {
      customers: {},
      conversations: {},
      metadata: {
        version: "2.0",
        lastUpdated: new Date().toISOString(),
        totalCustomers: 0,
      },
    };
  }

  async init(): Promise<void> {
    try {
      const dir = path.dirname(this.vaultPath);
      await fs.mkdir(dir, { recursive: true });

      const raw = await fs.readFile(this.vaultPath, "utf-8");
      this.data = JSON.parse(raw);
      console.log(
        `[Vault] Loaded ${Object.keys(this.data.customers).length} customers`
      );
    } catch {
      console.log("[Vault] No existing vault found, starting fresh");
      await this.persist();
    }
  }

  async saveCustomer(customer: CustomerRecord): Promise<void> {
    const isNew = !this.data.customers[customer.id];
    this.data.customers[customer.id] = customer;
    this.data.metadata.lastUpdated = new Date().toISOString();
    if (isNew) this.data.metadata.totalCustomers++;
    await this.persist();
  }

  async getCustomer(id: string): Promise<CustomerRecord | null> {
    return this.data.customers[id] ?? null;
  }

  async getAllCustomers(): Promise<CustomerRecord[]> {
    return Object.values(this.data.customers);
  }

  async getCustomersByStage(
    stage: CustomerRecord["stage"]
  ): Promise<CustomerRecord[]> {
    return Object.values(this.data.customers).filter(
      (c) => c.stage === stage
    );
  }

  async appendMessage(
    customerId: string,
    role: "user" | "assistant",
    content: string
  ): Promise<void> {
    if (!this.data.conversations[customerId]) {
      this.data.conversations[customerId] = [];
    }
    this.data.conversations[customerId].push({ role, content });
    await this.persist();
  }

  async getCustomerHistory(
    customerId: string
  ): Promise<Anthropic.MessageParam[]> {
    return this.data.conversations[customerId] ?? [];
  }

  async deleteCustomer(id: string): Promise<boolean> {
    if (!this.data.customers[id]) return false;
    delete this.data.customers[id];
    delete this.data.conversations[id];
    this.data.metadata.totalCustomers = Math.max(
      0,
      this.data.metadata.totalCustomers - 1
    );
    await this.persist();
    return true;
  }

  async searchCustomers(query: string): Promise<CustomerRecord[]> {
    const q = query.toLowerCase();
    return Object.values(this.data.customers).filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        (c.address ?? "").toLowerCase().includes(q) ||
        c.notes.some((n) => n.toLowerCase().includes(q))
    );
  }

  getStats(): {
    total: number;
    byStage: Record<string, number>;
    lastUpdated: string;
  } {
    const byStage: Record<string, number> = {};
    for (const c of Object.values(this.data.customers)) {
      byStage[c.stage] = (byStage[c.stage] ?? 0) + 1;
    }
    return {
      total: this.data.metadata.totalCustomers,
      byStage,
      lastUpdated: this.data.metadata.lastUpdated,
    };
  }

  private async persist(): Promise<void> {
    await fs.writeFile(this.vaultPath, JSON.stringify(this.data, null, 2));
  }
}
