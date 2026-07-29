"use client";

import Link from "next/link";
import type { Route } from "next";
import { useLocale } from "../lib/locale-context";

type Props = {
  title: { en: string; bn: string };
  description: { en: string; bn: string };
  available?: Array<{ en: string; bn: string }>;
  returnHref?: Route;
};

export function ServiceUnavailable({ title, description, available = [], returnHref = "/account" }: Props) {
  const { locale } = useLocale();
  const bn = locale === "bn";
  return (
    <section className="account-panel account-service-state" aria-labelledby="service-title">
      <span className="account-service-state__icon" aria-hidden>!</span>
      <div>
        <p className="eyebrow">{bn ? "সার্ভিস সংযোগ প্রয়োজন" : "Service connection required"}</p>
        <h1 id="service-title">{bn ? title.bn : title.en}</h1>
        <p>{bn ? description.bn : description.en}</p>
        {available.length ? <ul>{available.map(item => <li key={item.en}>{bn ? item.bn : item.en}</li>)}</ul> : null}
        <p className="account-service-state__note">
          {bn
            ? "এই স্ক্রিন কোনো তথ্য তৈরি বা সংরক্ষণ করার ভান করে না। প্রয়োজনীয় সুরক্ষিত API চালু হলে নিয়ন্ত্রণগুলো সক্রিয় হবে।"
            : "This screen does not pretend to create or save data. Controls will be enabled when the required secure API is available."}
        </p>
        <Link className="button button--ghost" href={returnHref}>{bn ? "অ্যাকাউন্টে ফিরুন" : "Back to account"}</Link>
      </div>
    </section>
  );
}
