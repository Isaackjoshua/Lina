import { Suspense } from "react";
import { getAdmin, githubConfigured, signIn, signOut } from "@/auth";
import { internalApi } from "@/lib/api";

type ApiStatus = {
  database: string;
  schema_revision: string | null;
  opportunities: number;
  sources: number;
};

export default function AdminPage({ searchParams }: PageProps<"/admin">) {
  return (
    <>
      <h1 className="text-2xl font-bold">Dashboard</h1>
      {/* The session is read per request, so it streams in behind this boundary. */}
      <Suspense fallback={<p className="mt-4 text-muted">Loading…</p>}>
        <AdminHome searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function AdminHome({ searchParams }: Pick<PageProps<"/admin">, "searchParams">) {
  const admin = await getAdmin();
  if (!admin) return <SignIn error={(await searchParams).error} />;

  return (
    <div className="mt-4 space-y-6">
      <p>
        Signed in as <strong>{admin}</strong>.
      </p>
      <ApiStatusPanel />
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/admin" });
        }}
      >
        <button className="rounded border border-line bg-white px-4 py-2">Sign out</button>
      </form>
    </div>
  );
}

async function ApiStatusPanel() {
  let status: ApiStatus | null = null;
  try {
    status = await internalApi<ApiStatus>("/status");
  } catch {
    // Shown below; the dashboard must still render when the API is down.
  }
  if (!status) {
    return <p className="rounded border-l-4 border-accent bg-white px-4 py-3">API unreachable.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-2 rounded border border-line bg-white p-4">
      <dt className="text-muted">Database</dt>
      <dd>{status.database}</dd>
      <dt className="text-muted">Schema revision</dt>
      <dd>{status.schema_revision ?? "none"}</dd>
      <dt className="text-muted">Opportunities</dt>
      <dd>{status.opportunities}</dd>
      <dt className="text-muted">Sources</dt>
      <dd>{status.sources}</dd>
    </dl>
  );
}

function SignIn({ error }: { error: string | string[] | undefined }) {
  return (
    <div className="mt-4 space-y-4">
      {error === "AccessDenied" && (
        <p className="rounded border-l-4 border-accent bg-white px-4 py-3">
          That GitHub account is not allowed here.
        </p>
      )}
      {githubConfigured ? (
        <form
          action={async () => {
            "use server";
            await signIn("github", { redirectTo: "/admin" });
          }}
        >
          <button className="rounded bg-brand px-4 py-2 font-medium text-white">
            Sign in with GitHub
          </button>
        </form>
      ) : (
        <p>
          GitHub login is not configured. Set <code>AUTH_GITHUB_ID</code>,{" "}
          <code>AUTH_GITHUB_SECRET</code> and <code>ADMIN_GITHUB_USERNAME</code> in{" "}
          <code>.env</code> (see the README).
        </p>
      )}
    </div>
  );
}
