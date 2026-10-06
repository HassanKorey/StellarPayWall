"use client";

import React, { useState } from "react";

const mockTransactions = [
  { endpoint: "/api/v1/generate", fee: "0.05", asset: "XLM", status: "Verified", time: "2s ago" },
  { endpoint: "/api/v1/search",   fee: "0.02", asset: "USDC", status: "Verified", time: "11s ago" },
  { endpoint: "/api/v1/analyze",  fee: "0.10", asset: "XLM", status: "Verified", time: "34s ago" },
  { endpoint: "/api/v1/embed",    fee: "0.01", asset: "USDC", status: "Verified", time: "1m ago" },
];

const apiKeys = [
  { key: "sk-stlr-a1b2c3d4", label: "Production App", calls: 1842, active: true },
  { key: "sk-stlr-e5f6g7h8", label: "Dev Sandbox",    calls: 312,  active: true },
  { key: "sk-stlr-i9j0k1l2", label: "AI Agent Bot",   calls: 5671, active: true },
  { key: "sk-stlr-m3n4o5p6", label: "Test Suite",     calls: 89,   active: false },
];

function StatCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className={`rounded-2xl p-6 border ${color} flex flex-col gap-1`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-3xl font-extrabold tracking-tight">{value}</p>
      <p className="text-xs opacity-60 mt-1">{sub}</p>
    </div>
  );
}

export default function MerchantAnalytics() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total XLM Revenue"
          value="1,245.50"
          sub="+12.4% this week"
          color="bg-blue-50 border-blue-200 text-blue-900"
        />
        <StatCard
          label="USDC Revenue (Soroban)"
          value="$850.00"
          sub="+8.1% this week"
          color="bg-emerald-50 border-emerald-200 text-emerald-900"
        />
        <StatCard
          label="Active API Keys"
          value="3"
          sub="1 inactive key"
          color="bg-violet-50 border-violet-200 text-violet-900"
        />
        <StatCard
          label="Total API Calls"
          value="7,914"
          sub="Across all endpoints"
          color="bg-amber-50 border-amber-200 text-amber-900"
        />
      </div>

      {/* API Keys Table */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-800">API Keys</h2>
          <button className="text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-1.5 rounded-lg transition-colors">
            + Generate Key
          </button>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-6 py-3 text-left">Label</th>
              <th className="px-6 py-3 text-left">Key</th>
              <th className="px-6 py-3 text-left">Calls</th>
              <th className="px-6 py-3 text-left">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {apiKeys.map((k) => (
              <tr key={k.key} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-3 font-medium text-gray-800">{k.label}</td>
                <td className="px-6 py-3">
                  <div className="flex items-center gap-2">
                    <code className="text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-600 font-mono">
                      {k.key.slice(0, 18)}…
                    </code>
                    <button
                      onClick={() => handleCopy(k.key)}
                      className="text-xs text-blue-500 hover:text-blue-700 transition-colors"
                    >
                      {copiedKey === k.key ? "✓ Copied" : "Copy"}
                    </button>
                  </div>
                </td>
                <td className="px-6 py-3 text-gray-600">{k.calls.toLocaleString()}</td>
                <td className="px-6 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${k.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {k.active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-800">Recent HTTP 402 Authorized Requests</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-6 py-3 text-left">Endpoint</th>
              <th className="px-6 py-3 text-left">Fee Paid</th>
              <th className="px-6 py-3 text-left">Asset</th>
              <th className="px-6 py-3 text-left">Time</th>
              <th className="px-6 py-3 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {mockTransactions.map((tx, i) => (
              <tr key={i} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-3 font-mono text-xs text-gray-700">{tx.endpoint}</td>
                <td className="px-6 py-3 font-medium text-gray-800">{tx.fee}</td>
                <td className="px-6 py-3">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${tx.asset === "XLM" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"}`}>
                    {tx.asset}
                  </span>
                </td>
                <td className="px-6 py-3 text-gray-400 text-xs">{tx.time}</td>
                <td className="px-6 py-3 text-right">
                  <span className="text-green-600 font-semibold text-xs">✓ Verified</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
