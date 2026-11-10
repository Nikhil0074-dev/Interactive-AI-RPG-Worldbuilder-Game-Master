"use client";
import { use } from "react";
import { GameLayout } from "@/components/GameLayout";

export default function CampaignPage({ params }: { params: Promise<{ campaignId: string }> }) {
  const { campaignId } = use(params);
  return <GameLayout campaignId={campaignId} />;
}
