"use client";
import { useEffect } from "react";
import { api, assetUrl } from "@/lib/api";
import { useGame } from "@/lib/store";

const GRADS: Record<string, string> = {
  ruined_city: "from-[#1b2430] to-[#3d5a6c]", ruined_tower: "from-[#1d1a26] to-[#4a3f63]",
  mountain_forest: "from-[#10201a] to-[#2f5d46]", underground_temple: "from-[#140f24] to-[#3b2d6e]",
};

/** Requests (cached, optional) location art; falls back to a gradient placeholder so text-only play always works. */
export function SceneArt({ entityId, biome, name, mood }: { entityId: string; biome: string; name: string; mood: string }) {
  const campaignId = useGame((s) => s.view?.campaign.id);
  const assetId = useGame((s) => s.view?.assets?.[entityId]);
  const setAsset = useGame((s) => s.setAsset);
  useEffect(() => {
    if (!campaignId || assetId) return;
    let live = true;
    api.requestAsset(campaignId, entityId).then((a) => { if (live && a.status === "ready") setAsset(entityId, a.id); }).catch(() => { /* art is optional */ });
    return () => { live = false; };
  }, [campaignId, entityId, assetId, setAsset]);
  return (
    <div className={`relative w-full aspect-[16/7] rounded-lg overflow-hidden border border-edge bg-gradient-to-b ${GRADS[biome] || GRADS.ruined_city}`} data-testid="scene-art">
      {assetId && /* eslint-disable-next-line @next/next/no-img-element */ <img src={assetUrl(assetId)} alt={`Illustration of ${name}`} className="absolute inset-0 w-full h-full object-cover fade-in" />}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent p-4 flex items-end justify-between">
        <h2 className="text-2xl text-parchment drop-shadow" data-testid="location-name">{name}</h2>
        <span className="text-xs uppercase tracking-widest text-gold border border-goldDim rounded px-2 py-0.5">{mood}</span>
      </div>
    </div>
  );
}

export function Portrait({ entityId, name, size = 56 }: { entityId: string; name: string; size?: number }) {
  const campaignId = useGame((s) => s.view?.campaign.id);
  const assetId = useGame((s) => s.view?.assets?.[entityId]);
  const setAsset = useGame((s) => s.setAsset);
  useEffect(() => {
    if (!campaignId || assetId) return;
    let live = true;
    api.requestAsset(campaignId, entityId).then((a) => { if (live && a.status === "ready") setAsset(entityId, a.id); }).catch(() => {});
    return () => { live = false; };
  }, [campaignId, entityId, assetId, setAsset]);
  return assetId
    // eslint-disable-next-line @next/next/no-img-element
    ? <img src={assetUrl(assetId)} alt={`Portrait of ${name}`} width={size} height={size} className="rounded-md border border-edge object-cover" style={{ width: size, height: size }} />
    : <div className="rounded-md border border-edge bg-panel2 flex items-center justify-center text-gold font-title" style={{ width: size, height: size }} aria-hidden>{name[0]}</div>;
}
