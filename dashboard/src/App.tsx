import { BrowserRouter, Routes, Route } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/components/layout";
import { DashboardPage } from "@/pages/dashboard";
import { LeiloesPage } from "@/pages/leiloes";
import { AnalisePage } from "@/pages/analise";
import { ComparativoPage } from "@/pages/comparativo";
import { RankingPage } from "@/pages/ranking";
import { AoVivoPage } from "@/pages/ao-vivo";
import { MercadoPage } from "@/pages/mercado";
import { ConfigPage } from "@/pages/config";

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/leiloes" element={<LeiloesPage />} />
            <Route path="/analise" element={<AnalisePage />} />
            <Route path="/comparativo" element={<ComparativoPage />} />
            <Route path="/ranking" element={<RankingPage />} />
            <Route path="/mercado" element={<MercadoPage />} />
            <Route path="/ao-vivo" element={<AoVivoPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  );
}
