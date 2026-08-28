import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Choose a New Password",
  description: "Complete SourceAI account recovery with a secure new password.",
  path: "/reset-password",
  noIndex: true,
});

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
