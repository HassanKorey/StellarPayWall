import MerchantAnalytics from "@/components/MerchantAnalytics";

export default function Home() {
  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-lg">
            ✦
          </div>
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
            StellarPayWall
          </h1>
        </div>
        <p className="text-gray-500 text-sm ml-12">
          HTTP 402 Micropayment Gateway · Merchant Analytics Dashboard
        </p>
      </div>

      <MerchantAnalytics />
    </main>
  );
}
