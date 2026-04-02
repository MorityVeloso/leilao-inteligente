import { useState, useEffect, useRef } from "react";
import { Settings, Upload, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ConfigPage() {
  const [cookieStatus, setCookieStatus] = useState<{
    configurado: boolean;
    bytes?: number;
    atualizado_em?: string;
  } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/cookies/status`)
      .then((r) => r.json())
      .then(setCookieStatus)
      .catch(() => setCookieStatus(null));
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMsg("");
    try {
      const body = await file.text();
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/cookies`,
        { method: "POST", body }
      );
      if (!res.ok) throw new Error(`Erro ${res.status}`);
      const data = await res.json();
      setMsg(`Cookies atualizados (${data.bytes} bytes)`);
      setCookieStatus({ configurado: true, bytes: data.bytes, atualizado_em: new Date().toISOString() });
    } catch (err) {
      setMsg(`Erro: ${err}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Configurações</h1>
        <p className="text-sm text-muted-foreground">
          Parâmetros do sistema e autenticação
        </p>
      </div>

      {/* Cookies YouTube */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Cookies do YouTube</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            O YouTube bloqueia downloads de servidores em datacenter. Os cookies autenticam
            o servidor como seu navegador. Exporte com:
          </p>
          <code className="block text-[10px] bg-muted px-3 py-2 rounded">
            yt-dlp --cookies-from-browser chrome --cookies cookies.txt
          </code>

          <div className="flex items-center gap-3">
            <input
              type="file"
              ref={fileRef}
              accept=".txt"
              onChange={handleUpload}
              className="hidden"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
            >
              <Upload className="h-3.5 w-3.5 mr-1.5" />
              {uploading ? "Enviando..." : "Enviar cookies.txt"}
            </Button>

            {cookieStatus && (
              <div className="flex items-center gap-1.5 text-xs">
                {cookieStatus.configurado ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                    <span className="text-green-500">Configurado</span>
                    <span className="text-muted-foreground">
                      ({((cookieStatus.bytes ?? 0) / 1024).toFixed(0)}KB
                      {cookieStatus.atualizado_em && ` — ${new Date(cookieStatus.atualizado_em).toLocaleDateString("pt-BR")}`})
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-red-500" />
                    <span className="text-red-500">Não configurado</span>
                  </>
                )}
              </div>
            )}
          </div>

          {msg && (
            <p className={`text-xs ${msg.startsWith("Erro") ? "text-red-500" : "text-green-500"}`}>
              {msg}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Settings className="h-10 w-10 mb-3 opacity-30" />
          <p className="text-sm font-medium">Mais configurações em breve</p>
          <p className="text-xs mt-1">Canais monitorados, parâmetros de processamento, notificações</p>
        </CardContent>
      </Card>
    </div>
  );
}
