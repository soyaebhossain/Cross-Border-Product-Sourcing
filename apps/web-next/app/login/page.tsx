"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginWithCredentials } from "../../lib/api";

export default function LoginPage(){const [identifier,setIdentifier]=useState("");const [password,setPassword]=useState("");const [loading,setLoading]=useState(false);const [error,setError]=useState("");const router=useRouter();
 const submit=async(e:React.FormEvent)=>{e.preventDefault();setLoading(true);setError("");try{await loginWithCredentials(identifier,password);router.push("/account/orders");router.refresh()}catch{setError("Invalid username, email, phone, or password.")}finally{setLoading(false)}};
 return <main className="shell shell--narrow"><section className="auth-card"><div><p className="eyebrow">Secure account</p><h1>Sign in to SourceAI</h1><p>Manage quotations, compare sourcing decisions and track cross-border orders.</p></div><form onSubmit={submit}><label>Username, email or phone<input autoComplete="username" value={identifier} onChange={e=>setIdentifier(e.target.value)} required/></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error?<div className="form-error" role="alert">{error}</div>:null}<button className="market-button" disabled={loading}>{loading?"Signing in…":"Sign in securely"}</button><small>Your session is stored in an HTTP-only cookie and is not exposed to browser scripts.</small></form></section></main>}
