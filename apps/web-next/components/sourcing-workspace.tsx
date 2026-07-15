"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getCheapestCountryRecommendation, type CheapestCountryRecommendation } from "../lib/api";

const names = { price:"Price", quality:"Quality", delivery:"Delivery", reliability:"Reliability", risk:"Low risk" };
export function SourcingWorkspace({ variantId }: { variantId: number }) {
  const [qty,setQty]=useState(10); const [weights,setWeights]=useState<Record<string,number>>({price:35,quality:20,delivery:15,reliability:15,risk:15});
  const [data,setData]=useState<CheapestCountryRecommendation|null>(null); const [loading,setLoading]=useState(true); const [error,setError]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>{setLoading(true);setError(false);getCheapestCountryRecommendation({variant_id:variantId,qty,weights}).then(setData).catch(()=>setError(true)).finally(()=>setLoading(false))},300);return()=>clearTimeout(timer)},[variantId,qty,weights]);
  return <section className="workspace"><div className="workspace-head"><div><span className="market-kicker">AI decision workspace</span><h2>Compare sourcing options</h2><p>Adjust your priorities. Rankings update using landed cost, supplier quality, delivery, reliability and risk.</p></div><label className="qty-control">Quantity<input type="number" min="1" value={qty} onChange={e=>setQty(Math.max(1,Number(e.target.value)||1))}/></label></div>
    <div className="weight-grid">{Object.entries(names).map(([key,label])=><label key={key}><span>{label}<b>{weights[key]}%</b></span><input type="range" min="0" max="100" value={weights[key]} onChange={e=>setWeights(v=>({...v,[key]:Number(e.target.value)}))}/></label>)}</div>
    {loading?<div className="workspace-loading">Recalculating the best sourcing routes…</div>:error?<div className="market-empty">Recommendation service is unavailable.</div>:<div className="supplier-table">{data?.recommendations.slice(0,5).map((item,i)=><article className={i===0?"supplier-option supplier-option--best":"supplier-option"} key={`${item.country.code}-${item.mode}`}><div className="supplier-rank">#{item.rank}</div><div><strong>{item.selected_offer.seller_name}</strong><span>{item.country.name} · {item.mode}</span></div><div><small>Landed cost</small><strong>BDT {Number(item.estimated_total_bdt).toLocaleString()}</strong></div><div><small>Delivery</small><strong>{item.eta.min_days}–{item.eta.max_days} days</strong></div><div><small>Score</small><strong>{Number(item.score).toFixed(1)}/100</strong></div><span className={`risk-badge risk-badge--${item.risk_level.toLowerCase()}`}>{item.risk_level} risk</span><p>{item.reason}{item.weaknesses.length?` Watch: ${item.weaknesses.join(", ")}.`:""}</p>{i===0?<span className="best-badge">Recommended</span>:null}</article>)}</div>}
    <div className="workspace-actions"><Link className="market-button" href={`/quote?variant=${variantId}&qty=${qty}`}>Request & save quote</Link><Link href="/account/saved-quotes">Compare saved quotes →</Link></div>
  </section>;
}
