import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const hostname = request.headers.get("host")?.split(":")[0]?.toLowerCase();
  const path = request.nextUrl.pathname;
  const isStudioHost = hostname === "studio.kumavoice.com";
  const isInternalPath =
    path.startsWith("/studio") ||
    path.startsWith("/api/") ||
    path.startsWith("/_next/");

  if (isStudioHost && !isInternalPath) {
    const destination = request.nextUrl.clone();
    destination.pathname = path === "/" ? "/studio" : `/studio${path}`;
    return NextResponse.rewrite(destination);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!.*\\..*).*)"],
};
