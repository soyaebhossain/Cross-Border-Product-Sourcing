import Card from "../../components/common/Card.jsx";
import { Link } from "react-router-dom";

const steps = [
  { title: "Describe your need", detail: "Search a product or drop SKU/BOM. We match offers across CN/SG/TH." },
  { title: "Compare lanes", detail: "See landed cost + ETA for Local (air) vs Bulk (sea). Pick the best fit." },
  { title: "Lock the order", detail: "Pay advance (bKash/manual now; gateway later). Ops verifies stock and QC." },
  { title: "Track & release", detail: "Milestones from purchase to customs to delivery/pickup. Pay remaining, receive items." },
];

export default function HowItWorks() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">How it works</h1>
        <p className="text-gray-600 text-sm mt-1">Decision-support marketplace for cross-border electronics.</p>
      </div>

      <Card className="grid gap-4 md:grid-cols-2">
        {steps.map((s, idx) => (
          <div key={s.title} className="flex gap-3">
            <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-white text-sm font-semibold">
              {idx + 1}
            </div>
            <div className="space-y-1">
              <div className="font-semibold text-slate-900">{s.title}</div>
              <div className="text-sm text-gray-600">{s.detail}</div>
            </div>
          </div>
        ))}
      </Card>

      <Card className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-300">Ready?</div>
          <div className="text-lg font-semibold">Start with a product or send your BOM.</div>
        </div>
        <div className="flex gap-3">
          <Link to="/products" className="rounded-xl bg-white px-4 py-2 text-slate-900 font-semibold shadow-sm">
            Browse products
          </Link>
          <Link
            to="/products?q="
            className="rounded-xl border border-white/30 bg-white/10 px-4 py-2 text-white transition hover:bg-white/20"
          >
            Build a quote
          </Link>
        </div>
      </Card>
    </div>
  );
}
