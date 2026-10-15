import type { Metadata } from "next";
import { PlatformPage } from "../components/marketing/platform-page";
export const metadata: Metadata = {
  title: "AegisOps Platform · Evidence, Approval & Response",
  description:
    "Explore scoped incident investigation, evidence review and human-approved staging response. Public previews use illustrative sample data.",
};
export default function Page() {
  return <PlatformPage />;
}
