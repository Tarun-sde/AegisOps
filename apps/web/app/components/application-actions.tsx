"use client";
import { useRouter } from "next/navigation";
import type { Service } from "../lib/api";
import { useFavorites } from "./app-shell";
import { Selector } from "./selector";
// DEC-386: original ProjectActions, with supported UUID-based destinations.
export function ApplicationActions({ service }: { service: Service }) {
  const { pinned, toggle } = useFavorites();
  const router = useRouter();
  const favorite = pinned.includes(service.id);
  return (
    <div className="ws-project-actions">
      <button
        className="ws-pin"
        aria-label={`${favorite ? "Unpin" : "Pin"} ${service.name}`}
        aria-pressed={favorite}
        onClick={() => toggle(service.id)}
        title={favorite ? "Remove favorite" : "Add favorite"}
      >
        <span aria-hidden="true">{favorite ? "★" : "☆"}</span>
      </button>
      <Selector
        compact
        menu
        label={`Actions for ${service.name}`}
        value="···"
        options={[
          {
            id: "favorite",
            label: favorite ? "Remove favorite" : "Add favorite",
            action: () => toggle(service.id),
          },
          ...[
            ["overview", "Open application"],
            ["analytics", "View analytics"],
            ["incidents", "View incidents"],
            ["settings", "Connection settings"],
            ["activity", "View activity"],
          ].map(([id, label]) => ({
            id,
            label,
            action: () => router.push(`/app/services/${service.id}?view=${id}`),
          })),
          {
            id: "copy-id",
            label: "Copy service ID",
            action: () => {
              if (typeof navigator !== "undefined" && navigator.clipboard) {
                void navigator.clipboard.writeText(service.id);
              }
            },
          },
          ...(service.healthcheck_url
            ? [
                {
                  id: "open-external",
                  label: "Open healthcheck URL ↗",
                  action: () => {
                    if (
                      typeof window !== "undefined" &&
                      service.healthcheck_url
                    ) {
                      window.open(
                        service.healthcheck_url,
                        "_blank",
                        "noopener,noreferrer",
                      );
                    }
                  },
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}
