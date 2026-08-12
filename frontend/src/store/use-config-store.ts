import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ProfileConfig = {
  name: string;
  headline: string;
  bio: string;
  email: string;
  linkedIn: string;
  github: string;
  avatar: string;
};

export type SettingsConfig = {
  linkedinHandle: string;
  llmProvider: string;
  openrouterModel: string;
  groqModel: string;
  huggingFaceModel: string;
  emailAddress: string;
  publishingMode: string;
  approvalMode: string;
  theme: string;
};

type ConfigState = {
  profile: ProfileConfig;
  settings: SettingsConfig;
  updateProfile: (profile: Partial<ProfileConfig>) => void;
  updateSettings: (settings: Partial<SettingsConfig>) => void;
};

const defaultProfile: ProfileConfig = {
  name: "LinkedIn Creator",
  headline: "Product marketer",
  bio: "Clear, experienced, premium",
  email: "creator@example.com",
  linkedIn: "linkedin.com/in/creator",
  github: "github.com/creator",
  avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
};

const defaultSettings: SettingsConfig = {
  linkedinHandle: "@creator",
  llmProvider: "OpenRouter",
  openrouterModel: "openai/gpt-4.1-mini",
  groqModel: "llama-3.3-70b-versatile",
  huggingFaceModel: "google/gemma-2-9b-it",
  emailAddress: "creator@example.com",
  publishingMode: "manual-review",
  approvalMode: "email",
  theme: "dark",
};

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      profile: defaultProfile,
      settings: defaultSettings,
      updateProfile: (profile) =>
        set((state) => ({ profile: { ...state.profile, ...profile } })),
      updateSettings: (settings) =>
        set((state) => ({ settings: { ...state.settings, ...settings } })),
    }),
    {
      name: "linkedin-ai-studio-config",
    },
  ),
);
