"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { signInWithGoogle } from "@/lib/firebase";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.push("/dashboard");
  }, [user, loading, router]);

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;

  return (
    <main className="flex flex-col items-center justify-center min-h-screen gap-8 px-4">
      <div className="text-center">
        <h1 className="text-5xl font-bold mb-3">Circles</h1>
        <p className="text-gray-500 text-lg">Study together. Quiz together.</p>
      </div>
      <button
        onClick={signInWithGoogle}
        className="flex items-center gap-3 px-6 py-3 bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition font-medium"
      >
        <img src="https://www.google.com/favicon.ico" className="w-5 h-5" alt="Google" />
        Sign in with Google
      </button>
    </main>
  );
}
