import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Reset Your Password",
  description: "Request a secure, time-limited link to reset your SourceAI password.",
  path: "/forgot-password",
  noIndex: true,
});

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
