"use client";

import Image from "next/image";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConfigStore } from "@/store/use-config-store";

export default function ProfilePage() {
  const { profile, updateProfile } = useConfigStore();

  function handleSave() {
    toast.success("Profile saved");
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Profile</h1>
          <p className="text-zinc-400">Creator identity, preferences, and publishing details.</p>
        </div>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Profile Overview</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-3">
              <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5">
                <Image src={profile.avatar} alt="Profile avatar" width={320} height={320} className="h-72 w-full object-cover" />
              </div>
            </div>

            <div className="space-y-3 text-zinc-300">
              <div>
                <label className="mb-2 block text-sm">Name</label>
                <Input value={profile.name} onChange={(event) => updateProfile({ name: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Headline</label>
                <Input value={profile.headline} onChange={(event) => updateProfile({ headline: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Bio</label>
                <Textarea value={profile.bio} onChange={(event) => updateProfile({ bio: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Email</label>
                <Input value={profile.email} onChange={(event) => updateProfile({ email: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">LinkedIn</label>
                <Input value={profile.linkedIn} onChange={(event) => updateProfile({ linkedIn: event.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">GitHub</label>
                <Input value={profile.github} onChange={(event) => updateProfile({ github: event.target.value })} />
              </div>
              <Button onClick={handleSave}>Save Profile</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
