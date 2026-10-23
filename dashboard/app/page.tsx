"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";

export default function Root() {
  const router = useRouter();
  useEffect(() => {
    const token = Cookies.get("ag_token");
    router.replace(token ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
