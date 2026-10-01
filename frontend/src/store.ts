import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEMO_SPEC, type AppSpec } from "@appforge/app-spec";

export type Version = {
  id: string;
  parentId: string | null;
  summary: string;
  spec: AppSpec;
  prompt?: string;
  plan?: any;
  results?: any[];
  criticIssues?: any[];
  criticApproved?: boolean | null;
  createdAt: number;
};

const STARTER_VERSION: Version = {
  id: "v1",
  parentId: null,
  summary: DEMO_SPEC.meta.name,
  spec: DEMO_SPEC,
  prompt: "Tell me if I can bunk tomorrow and still keep 75% attendance",
  plan: {
    plan: {
      problem: "Student wants to calculate whether they can bunk class tomorrow while keeping >=75% minimum attendance.",
      primary_question: "Can I bunk tomorrow?",
      features: ["Conducted & attended tracker", "Configurable target attendance slider", "Recovery lectures count", "Future projection chart"]
    },
    contract: {
      state: [
        { id: "conducted", label: "Conducted", type: "int", default: 64, min: 0, max: 1000 },
        { id: "attended", label: "Attended", type: "int", default: 53, min: 0, max: 1000 },
        { id: "target", label: "Target %", type: "percent", default: 75, min: 1, max: 99 }
      ],
      outputs: [
        { id: "attendance_pct", label: "Current attendance %" },
        { id: "max_skippable", label: "Lectures you can skip" },
        { id: "can_skip_tomorrow", label: "Can skip tomorrow" }
      ],
      actions: [
        { id: "skip_tomorrow", label: "Simulate: skip tomorrow" },
        { id: "attend_tomorrow", label: "Simulate: attend tomorrow" }
      ]
    }
  },
  results: [
    { layer: "invariant", name: "No NaN/Infinity: defaults", pass: true },
    { layer: "invariant", name: "No NaN/Infinity: min/max limits", pass: true },
    { layer: "example", name: "Reference: 53/64 at 75%", pass: true },
    { layer: "fuzz", name: "100 random in-range inputs stay finite", pass: true }
  ],
  criticIssues: [],
  criticApproved: true,
  createdAt: 1710000000000,
};

type StoreState = {
  versions: Version[];
  currentId: string | null;
  add: (
    summary: string,
    spec: AppSpec,
    details?: {
      prompt?: string;
      plan?: any;
      results?: any[];
      criticIssues?: any[];
      criticApproved?: boolean | null;
    }
  ) => void;
  select: (id: string) => void;
  clear: () => void;
};

// Persistent version tree in localStorage under 'appforge-swarm-v2'
export const useStore = create<StoreState>()(
  persist(
    (set, get) => ({
      versions: [STARTER_VERSION],
      currentId: "v1",

      add: (summary, spec, details = {}) => {
        const currentVersions = get().versions;
        const id = "v" + (currentVersions.length + 1);
        const newVersion: Version = {
          id,
          parentId: get().currentId,
          summary: summary || spec.meta.name || "Mini App",
          spec,
          prompt: details.prompt,
          plan: details.plan,
          results: details.results,
          criticIssues: details.criticIssues,
          criticApproved: details.criticApproved,
          createdAt: Date.now(),
        };

        set({
          versions: [...currentVersions, newVersion],
          currentId: id,
        });
      },

      select: (id) => set({ currentId: id }),

      clear: () => set({ versions: [], currentId: null }),
    }),
    {
      name: "appforge-swarm-v2",
    }
  )
);
