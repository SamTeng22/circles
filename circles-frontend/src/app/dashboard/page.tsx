"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { circlesApi, Circle } from "@/lib/api";
import { logout } from "@/lib/firebase";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [circles, setCircles] = useState<Circle[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.push("/");
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      circlesApi.list().then(setCircles).catch(console.error);
    }
  }, [user]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const circle = await circlesApi.create(newName, newDesc);
      setCircles([circle, ...circles]);
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleJoin = async () => {
    if (!inviteCode.trim()) return;
    try {
      const circle = await circlesApi.join(inviteCode.trim().toUpperCase());
      setCircles([circle, ...circles]);
      setShowJoin(false);
      setInviteCode("");
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Circles</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.displayName}</span>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold">Your circles</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setShowJoin(true)}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
            >
              Join circle
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-gray-800"
            >
              New circle
            </button>
          </div>
        </div>

        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

        {circles.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No circles yet</p>
            <p className="text-sm mt-1">Create one or join with an invite code</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {circles.map((c) => (
              <div
                key={c.id}
                onClick={() => router.push(`/circles/${c.id}`)}
                className="bg-white border border-gray-100 rounded-xl p-5 cursor-pointer hover:border-gray-300 transition"
              >
                <h3 className="font-semibold">{c.name}</h3>
                {c.description && <p className="text-sm text-gray-500 mt-1">{c.description}</p>}
                <p className="text-xs text-gray-400 mt-2">Code: {c.invite_code}</p>
              </div>
            ))}
          </div>
        )}

        {/* Create modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4">
              <h3 className="font-semibold text-lg mb-4">Create a circle</h3>
              <input
                className="w-full border rounded-lg px-3 py-2 mb-3 text-sm"
                placeholder="Circle name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <input
                className="w-full border rounded-lg px-3 py-2 mb-4 text-sm"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-500">Cancel</button>
                <button onClick={handleCreate} className="px-4 py-2 bg-black text-white rounded-lg text-sm">Create</button>
              </div>
            </div>
          </div>
        )}

        {/* Join modal */}
        {showJoin && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4">
              <h3 className="font-semibold text-lg mb-4">Join a circle</h3>
              <input
                className="w-full border rounded-lg px-3 py-2 mb-4 text-sm uppercase tracking-widest"
                placeholder="Invite code"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowJoin(false)} className="px-4 py-2 text-sm text-gray-500">Cancel</button>
                <button onClick={handleJoin} className="px-4 py-2 bg-black text-white rounded-lg text-sm">Join</button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
