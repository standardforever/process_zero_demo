"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getSchemaStoreStatus } from "@/lib/api";

export default function RulesNavLink() {
  const [canUseChat, setCanUseChat] = useState(false);

  useEffect(() => {
    let canceled = false;

    async function loadStatus() {
      try {
        const status = await getSchemaStoreStatus();
        if (!canceled) {
          setCanUseChat(Boolean(status.can_use_chat));
        }
      } catch {
        if (!canceled) {
          setCanUseChat(false);
        }
      }
    }

    void loadStatus();
    return () => {
      canceled = true;
    };
  }, []);

  if (canUseChat) {
    return (
      <Link href="/rules" className="rounded-md px-3 py-1 hover:bg-slate-100">
        Rules Chat
      </Link>
    );
  }

  return (
    <button
      type="button"
      disabled
      title="Locked: add ERP column, CRM column, and one notification email in Schema."
      className="cursor-not-allowed rounded-md px-3 py-1 text-slate-400">
      Rules Chat
    </button>
  );
}
