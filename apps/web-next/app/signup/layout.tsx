import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Create an Account",
  description: "Create a SourceAI customer account to save quotes and manage sourcing orders.",
  path: "/signup",
  noIndex: true,
});

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
