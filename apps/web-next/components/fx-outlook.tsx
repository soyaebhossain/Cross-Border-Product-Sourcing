"use client";

import type { FxOutlook } from "../lib/api";
import { formatBdt } from "../lib/format";

export function FxOutlookPanel({ outlook, bn, intlLocale }: { outlook?: FxOutlook | null; bn: boolean; intlLocale: string }) {
  if (!outlook) return null;
  const number = (value: number | undefined, digits = 2) =>
    value === undefined ? "—" : new Intl.NumberFormat(intlLocale, { maximumFractionDigits: digits }).format(value);
  if (!outlook.available) {
    return (
      <article className="form-card pricing-provenance" aria-labelledby="fx-outlook-title">
        <p className="eyebrow">{bn ? "বিনিময় হারের পূর্বাভাস" : "Exchange-rate outlook"}</p>
        <h2 id="fx-outlook-title">{bn ? "পূর্বাভাসের জন্য যথেষ্ট ইতিহাস নেই" : "Not enough history for an outlook yet"}</h2>
        <small className="pricing-provenance__footer">
          {bn ? `${outlook.currency}-এর ${outlook.history_points} দিনের তথ্য আছে; অন্তত ৩০ দিন দরকার।` : `${outlook.history_points} daily ${outlook.currency} rates stored; at least 30 are needed.`}
        </small>
      </article>
    );
  }
  const backtest = outlook.backtest;
  return (
    <article className="form-card pricing-provenance" aria-labelledby="fx-outlook-title">
      <div className="section__header">
        <div>
          <p className="eyebrow">{bn ? `${outlook.horizon_days} দিনের বিনিময় হারের পূর্বাভাস` : `${outlook.horizon_days}-day exchange-rate outlook`}</p>
          <h2 id="fx-outlook-title">
            {bn ? "খরচ কতটা বদলাতে পারে" : "How much this cost could move"}
          </h2>
        </div>
        <span className="admin-status admin-status--neutral">{bn ? "অনুমান, নিশ্চয়তা নয়" : "Estimate, not a guarantee"}</span>
      </div>
      <ul className="pricing-provenance__list">
        <li>
          <div>
            <strong>{bn ? "সম্ভাব্য ল্যান্ডেড কস্ট" : "Likely landed cost range"}</strong>
            <small>{bn ? "৯০% সম্ভাবনার সীমা; শুধু বিনিময় হারের প্রভাব" : "90% interval; exchange-rate effect only"}</small>
          </div>
          <div className="pricing-provenance__status">
            <span>{formatBdt(outlook.total_low_bdt, intlLocale)} – {formatBdt(outlook.total_high_bdt, intlLocale)}</span>
          </div>
        </li>
        <li>
          <div>
            <strong>1 {outlook.currency} → BDT</strong>
            <small>{bn ? `এখন ৳${number(outlook.last_rate_to_bdt)}` : `Now ৳${number(outlook.last_rate_to_bdt)}`}</small>
          </div>
          <div className="pricing-provenance__status">
            <span>৳{number(outlook.low_rate_to_bdt)} – ৳{number(outlook.high_rate_to_bdt)}</span>
            <small>{number(outlook.low_change_percent)}% {bn ? "থেকে" : "to"} +{number(outlook.high_change_percent)}%</small>
          </div>
        </li>
      </ul>
      <small className="pricing-provenance__footer">
        {bn
          ? `পদ্ধতি: দৈনিক পরিবর্তনের ওপর random walk with drift। তথ্য: ${outlook.history_points} দিনের প্রকৃত হার (${outlook.history_from} থেকে ${outlook.history_to}), উৎস ${outlook.source}।`
          : `Method: random walk with drift on daily changes. Data: ${outlook.history_points} observed daily rates (${outlook.history_from} to ${outlook.history_to}) from ${outlook.source}.`}
        {backtest
          ? (bn
            ? ` অতীত যাচাই: ${backtest.forecasts_scored}টি পূর্বাভাসে গড় ভুল ${number(backtest.mean_absolute_percent_error)}%, সীমার ভেতরে পড়েছে ${number(backtest.interval_coverage_percent, 1)}%।`
            : ` Backtest: ${backtest.forecasts_scored} past forecasts, mean error ${number(backtest.mean_absolute_percent_error)}%, ${number(backtest.interval_coverage_percent, 1)}% inside the interval.`)
          : ""}
      </small>
    </article>
  );
}
