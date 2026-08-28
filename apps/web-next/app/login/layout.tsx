import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Secure Sign In",
  description: "Sign in securely to manage SourceAI quotes, orders, and account details.",
  path: "/login",
  noIndex: true,
});

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
