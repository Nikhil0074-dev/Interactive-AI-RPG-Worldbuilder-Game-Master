"use client";
import { useEffect } from "react";

/** Applies the saved "reduce motion" preference on every page. */
export function MotionInit() {
  useEffect(() => { document.documentElement.dataset.reduceMotion = String(localStorage.getItem("rpg_reduce_motion") === "true"); }, []);
  return null;
}
