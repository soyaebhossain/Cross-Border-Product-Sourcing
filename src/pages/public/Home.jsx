import { useState } from "react";
import Card from "../../components/common/Card.jsx";
import { Link, useNavigate } from "react-router-dom";

const featureCards = [
  {
    title: "Hands-on sourcing desk",
    copy: "Operators confirm MOQ, packaging, and compliance before you commit. No more WeChat back-and-forth.",
    to: "/how-it-works",
    icon: "HS",
  },
  {
    title: "Transparent landed cost",
    copy: "See duty, freight, and handling in one view. Adjust quantity or lane and watch the math update instantly.",
    to: "/products",
    icon: "LC",
  },
  {
    title: "QC + dispute guard",
    copy: "Pre-ship inspection and photo proof are built in. Funds only release after your acceptance.",
    to: "/how-it-works",
    icon: "QC",
  },
  {
    title: "Lane recommendation (AI-lite)",
    copy: "Suggests CN/SG/TH + Local/Bulk based on ETA vs cost priority. Swaps if offers expire or stock drops.",
    to: "/products",
    icon: "AI",
  },
  {
    title: "Payment controls",
    copy: "Manual bKash/Nagad capture now; gateway next. Advance vs remaining tracked with verification steps.",
    to: "/how-it-works",
    icon: "$",
  },
  {
    title: "AI sourcing copilot",
    copy: "Chatbot answers HS codes, landed cost, and lane fit in seconds. Auto-escalates to operators when confidence is low.",
    action: "openCopilot",
    icon: "Bot",
  },
];

const lanes = [
  { name: "Shenzhen -> Dhaka", eta: "6-8 days air", note: "Best for wearables & phones", badge: "CN", accent: "from-amber-400 to-orange-500", signal: "QC + repack included" },
  { name: "Bangkok -> Dhaka", eta: "5-7 days", note: "Low duty window for accessories", badge: "TH", accent: "from-teal-400 to-emerald-500", signal: "Local pickup option" },
  { name: "Singapore -> Dhaka", eta: "4-6 days", note: "Fastest for high-value chips", badge: "SG", accent: "from-blue-400 to-indigo-500", signal: "Bonded transfer ready" },
];

const steps = [
  { title: "Share your SKU or BOM", detail: "Drop a link or upload a spec. We surface vetted factories with MOQ, lead time, and alternates." },
  { title: "Pick the right lane", detail: "Compare CN / SG / TH on duty, speed, and packaging. Lock QC, insurance, and delivery address." },
  { title: "Ship with visibility", detail: "Milestones from consolidation to last mile. Dispute handling and payouts live in one dashboard." },
];

export default function Home() {
  const navigate = useNavigate();
  const [showCopilotModal, setShowCopilotModal] = useState(false);

  const handleOpenCopilot = () => setShowCopilotModal(true);
  const handleStartCopilot = () => {
    setShowCopilotModal(false);
    navigate("/products?q=ai");
  };

  return (
    <div className="space-y-12">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white shadow-xl">
        <div className="absolute inset-0">
          <div className="absolute -left-16 top-10 h-40 w-40 rounded-full bg-emerald-400/20 blur-3xl" />
          <div className="absolute bottom-0 right-10 h-48 w-48 rounded-full bg-indigo-400/20 blur-3xl" />
        </div>
        <div className="relative grid gap-10 p-8 md:grid-cols-2 md:p-12">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-200">
              Cross-border sourcing
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold leading-tight md:text-4xl">Electronics supply across Asia without the friction.</h1>
              <p className="text-slate-200">Compare China, Singapore, and Thailand lanes, lock the right Incoterm, and keep QC + payments in one place. Less chasing, more control.</p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link to="/products" className="inline-flex items-center justify-center rounded-xl bg-white px-5 py-3 text-slate-900 font-semibold shadow-lg shadow-white/10 transition hover:-translate-y-0.5 hover:shadow-xl">
                Browse live catalog
              </Link>
              <Link to="/products?q=" className="inline-flex items-center justify-center rounded-xl border border-white/20 bg-white/5 px-5 py-3 text-white transition hover:-translate-y-0.5 hover:bg-white/10">
                Build a quote
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { label: "Lane coverage", value: "CN / SG / TH" },
                { label: "Avg. lead time", value: "4-12 days" },
                { label: "Typical savings", value: "12-22%" },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                  <div className="text-xs uppercase tracking-wide text-slate-300">{item.label}</div>
                  <div className="text-lg font-semibold">{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/15 bg-white/5 p-5 backdrop-blur lane-board">
            <div className="flex items-center justify-between text-sm text-slate-200">
              <span className="font-semibold text-white">Lane board</span>
              <span className="rounded-full bg-white/10 px-3 py-1 text-xs">Live ETA</span>
            </div>
            <div className="mt-4 space-y-3">
              {lanes.map((lane) => (
                <div key={lane.name} className="flex items-start gap-4 rounded-xl border border-white/10 bg-white/5 px-4 py-3 shadow-inner lane-card">
                  <div className={`lane-badge-dark flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${lane.accent} text-base font-semibold shadow`}>
                    {lane.badge}
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between text-sm text-white">
                      <span className="font-semibold">{lane.name}</span>
                      <span className="lane-eta-dark rounded-full px-2 py-1 text-xs font-semibold">{lane.eta}</span>
                    </div>
                    <div className="text-xs text-slate-200">{lane.note}</div>
                    <div className="flex items-center gap-2 text-xs text-emerald-200 whitespace-nowrap">
                      <span className="h-2 w-2 rounded-full bg-emerald-300" />
                      <span>{lane.signal}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Operators double-check factory capacity, HS code, and packaging before funds move.
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {featureCards.map((card) => (
          <Card key={card.title} className="h-full transform transition hover:-translate-y-1 hover:shadow-lg hover:shadow-slate-100/60">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-3 flex-1">
                <div className="text-lg font-semibold text-slate-900">{card.title}</div>
                <p className="text-sm text-gray-600 leading-relaxed">{card.copy}</p>
                {card.to && (
                  <Link to={card.to} className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700 hover:text-slate-900">
                    Learn more <span aria-hidden>&gt;</span>
                  </Link>
                )}
                {card.action === "openCopilot" && (
                  <button
                    type="button"
                    onClick={handleOpenCopilot}
                    className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700 hover:text-slate-900"
                  >
                    Try the copilot <span aria-hidden>&gt;</span>
                  </button>
                )}
              </div>
              <div className="shrink-0">
                {card.to ? (
                  <Link
                    to={card.to}
                    className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white text-xs font-semibold transition hover:-translate-y-0.5 hover:bg-slate-800"
                    aria-label={`Open ${card.title}`}
                  >
                    <span aria-hidden>{card.icon || ">"}</span>
                  </Link>
                ) : card.action === "openCopilot" ? (
                  <button
                    type="button"
                    onClick={handleOpenCopilot}
                    className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white text-xs font-semibold transition hover:-translate-y-0.5 hover:bg-slate-800"
                    aria-label={`Open ${card.title}`}
                  >
                    <span aria-hidden>{card.icon || ">"}</span>
                  </button>
                ) : (
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-slate-900 text-white text-xs font-semibold">
                    {card.icon || ">"}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3 bg-gradient-to-br from-white to-slate-50 routes-card">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Routes & cost</div>
              <div className="text-xl font-semibold text-slate-900">Pick the lane that fits the shipment</div>
            </div>
            <Link to="/products" className="text-sm text-slate-700 underline underline-offset-4">
              View catalog
            </Link>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {lanes.map((lane) => (
              <div key={lane.name} className="rounded-2xl border border-slate-100 bg-white px-4 py-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-slate-900">{lane.name}</span>
                  <span className="routes-eta inline-flex items-center justify-center rounded-lg bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-900">
                    {lane.eta}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-600">{lane.note}</div>
                <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700 whitespace-nowrap">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>{lane.signal}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Workflow</div>
          <div className="text-xl font-semibold text-slate-900">How we move your order</div>
          <div className="mt-4 space-y-4">
            {steps.map((step, idx) => (
              <div key={step.title} className="flex gap-3">
                <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                  {idx + 1}
                </div>
                <div className="space-y-1">
                  <div className="font-semibold text-slate-900">{step.title}</div>
                  <p className="text-sm text-gray-600 leading-relaxed">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <Card className="flex flex-col gap-3 items-start md:flex-row md:items-center md:justify-between bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-300">Need something specific?</div>
          <div className="text-xl font-semibold">Send your BOM and get factory picks today.</div>
          <div className="text-sm text-slate-200 mt-1">Local delivery options for Dhaka, Chattogram, and beyond.</div>
        </div>
        <div className="flex gap-3">
          <Link to="/products?q=" className="rounded-xl bg-white px-4 py-2 text-slate-900 font-semibold shadow-sm">
            Request a quote
          </Link>
          <Link to="/products" className="rounded-xl border border-white/30 bg-white/10 px-4 py-2 text-white transition hover:bg-white/20">
            Browse products
          </Link>
        </div>
      </Card>

      {showCopilotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">AI sourcing copilot</div>
                <div className="text-xl font-semibold text-slate-900">Instant answers, human escalation ready</div>
                <p className="text-sm text-gray-600 mt-1">
                  Ask about HS codes, landed cost, best lane, or packaging. We cite sources and hand off to operators if confidence is low.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCopilotModal(false)}
                className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-200"
                aria-label="Close copilot preview"
              >
                Close
              </button>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 space-y-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sample chat</div>
                <div className="space-y-2 text-sm text-slate-800">
                  <div className="rounded-lg bg-white p-3 shadow-sm">
                    Buyer: Need HS code + landed cost for 500 smartwatches to Dhaka.
                  </div>
                  <div className="rounded-lg bg-slate-900 p-3 text-white shadow-sm">
                    Copilot: HS code 9102.11. Estimated duty + VAT: 26-28%. Best lane: SG → DAC (5-6 days) with QC + repack. Want a formal quote?
                  </div>
                  <div className="rounded-lg bg-white p-3 shadow-sm">
                    Buyer: Add drop test requirement.
                  </div>
                  <div className="rounded-lg bg-slate-900 p-3 text-white shadow-sm">
                    Copilot: Added ISTA 1A drop test. Estimated cost +2.5%. Escalating to an operator for final confirmation.
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-100 bg-white p-4 space-y-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">What it does</div>
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                  <li>Understands Bengali + English, keeps context.</li>
                  <li>Retrieves HS codes, duty, and lane options from your docs.</li>
                  <li>Exports a structured quote request for operators.</li>
                  <li>Auto-escalates when confidence is low or data is missing.</li>
                </ul>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleStartCopilot}
                    className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-white text-sm font-semibold hover:-translate-y-0.5 hover:bg-slate-800 transition"
                  >
                    Open copilot
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCopilotModal(false)}
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                  >
                    Maybe later
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
