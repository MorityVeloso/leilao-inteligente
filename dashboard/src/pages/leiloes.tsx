import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Play, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";

export function LeiloesPage() {
  const { data: leiloes = [], isLoading: loading } = useQuery({
    queryKey: ["leiloes"],
    queryFn: () => api.leiloes(),
  });
  const [url, setUrl] = useState("");
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leilões</h1>
          <p className="text-sm text-muted-foreground">
            Leilões processados e novos processamentos
          </p>
        </div>
      </div>

      {/* Processar novo */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Processar novo leilão</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Cole a URL do YouTube (ex: https://www.youtube.com/live/...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1"
            />
            <Button disabled={!url.trim()}>
              <Play className="h-4 w-4 mr-2" />
              Processar
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            O processamento leva ~2 minutos por leilão de 5 horas
          </p>
        </CardContent>
      </Card>

      {/* Lista */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Leilões processados ({leiloes.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-[200px] text-muted-foreground">
              Carregando...
            </div>
          ) : leiloes.length === 0 ? (
            <div className="flex items-center justify-center h-[200px] text-muted-foreground">
              Nenhum leilão processado ainda
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titulo</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead>Local</TableHead>
                  <TableHead className="text-right">Lotes</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leiloes.map((leilao) => (
                  <TableRow
                    key={leilao.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/leiloes/${leilao.id}`)}
                  >
                    <TableCell className="font-medium max-w-[300px] truncate">
                      {leilao.titulo}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {leilao.canal}
                    </TableCell>
                    <TableCell>
                      {leilao.local_cidade && leilao.local_estado ? (
                        <span className="flex items-center gap-1 text-sm">
                          <MapPin className="h-3 w-3" />
                          {leilao.local_cidade}-{leilao.local_estado}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {leilao.total_lotes ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {leilao.processado_em
                        ? new Date(leilao.processado_em).toLocaleDateString("pt-BR")
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          leilao.status === "completo"
                            ? "bg-green-500/10 text-green-500"
                            : "bg-yellow-500/10 text-yellow-500"
                        }
                      >
                        {leilao.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
