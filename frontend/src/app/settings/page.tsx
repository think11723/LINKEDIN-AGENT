"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useConfigStore } from "@/store/use-config-store";

export default function SettingsPage() {
  const { settings, updateSettings } = useConfigStore();

  function handleSave() {
    toast.success("Settings updated");
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Settings</h1>
          <p className="text-zinc-400">Tune the workspace for your publishing workflow.</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-2 block text-sm">LinkedIn Handle</label>
                <Input value={settings.linkedinHandle} onChange={(event) => updateSettings({ linkedinHandle: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Email</label>
                <Input value={settings.emailAddress} onChange={(event) => updateSettings({ emailAddress: event.target.value })} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>LLM Provider</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-2 block text-sm">Primary Provider</label>
                <Input value={settings.llmProvider} onChange={(event) => updateSettings({ llmProvider: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">OpenRouter Model</label>
                <Input value={settings.openrouterModel} onChange={(event) => updateSettings({ openrouterModel: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Groq Model</label>
                <Input value={settings.groqModel} onChange={(event) => updateSettings({ groqModel: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">HuggingFace Model</label>
                <Input value={settings.huggingFaceModel} onChange={(event) => updateSettings({ huggingFaceModel: event.target.value })} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Publishing & Approval</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-2 block text-sm">Publishing Mode</label>
                <Input value={settings.publishingMode} onChange={(event) => updateSettings({ publishingMode: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Approval Mode</label>
                <Input value={settings.approvalMode} onChange={(event) => updateSettings({ approvalMode: event.target.value })} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Theme</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-2 block text-sm">Theme</label>
                <Input value={settings.theme} onChange={(event) => updateSettings({ theme: event.target.value })} />
              </div>
              <Button variant="outline" onClick={handleSave}>Save Preferences</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
