import { Radio } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function AoVivoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ao Vivo</h1>
        <p className="text-sm text-muted-foreground">
          Acompanhamento de leiloes em tempo real
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Radio className="h-12 w-12 mb-4 opacity-30" />
          <p className="text-lg font-medium">Em breve</p>
          <p className="text-sm mt-1">
            Modo ao vivo com comparacao historica em tempo real
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
