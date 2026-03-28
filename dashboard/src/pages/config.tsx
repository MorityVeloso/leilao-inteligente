import { Settings } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ConfigPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Configuracoes</h1>
        <p className="text-sm text-muted-foreground">
          Canais monitorados e parametros de processamento
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Settings className="h-12 w-12 mb-4 opacity-30" />
          <p className="text-lg font-medium">Em breve</p>
          <p className="text-sm mt-1">
            Configuracao de canais YouTube, API key e intervalos
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
