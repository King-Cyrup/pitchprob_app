import { NextResponse } from "next/server";
import { getMatch } from "@/lib/api";

/** Proxy the FastAPI match-details endpoint so the client can fetch it directly. */
export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!/^\d+$/.test(id) || Number(id) <= 0) {
    return NextResponse.json({ detail: "Match not found" }, { status: 404 });
  }
  try {
    const match = await getMatch(Number(id));
    return NextResponse.json(match);
  } catch (error) {
    if (error instanceof Error && error.message.includes("404")) {
      return NextResponse.json({ detail: "Match not found" }, { status: 404 });
    }
    return NextResponse.json({ detail: "The match data service could not be reached." }, { status: 502 });
  }
}
