import { cookies } from "next/headers";

import { AccountPage } from "@/features/account/components/account-page";
import { readSessionExpiry } from "@/lib/session/cookies";

export default async function Page() {
  const cookieStore = await cookies();

  return <AccountPage sessionExpiresAt={readSessionExpiry(cookieStore)} />;
}
