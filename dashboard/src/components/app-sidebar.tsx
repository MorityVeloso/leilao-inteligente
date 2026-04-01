import { useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  ClipboardList,
  LineChart,
  Scale,
  Trophy,
  Radio,
  Settings,
  Beef,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { title: "Dashboard", icon: BarChart3, path: "/" },
  { title: "Leilões", icon: ClipboardList, path: "/leiloes" },
  { title: "Análise", icon: LineChart, path: "/analise" },
  { title: "Comparativo", icon: Scale, path: "/comparativo" },
  { title: "Ranking", icon: Trophy, path: "/ranking" },
  { title: "Ao Vivo", icon: Radio, path: "/ao-vivo" },
];

const FOOTER_ITEMS = [
  { title: "Configurações", icon: Settings, path: "/config" },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <Sidebar collapsible="icon" className="dark border-r-0">
      <SidebarHeader className="p-4">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              onClick={() => navigate("/")}
              className="hover:bg-sidebar-accent"
            >
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-green-600 text-white">
                <Beef className="size-4" />
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-semibold text-sm">Leilão Inteligente</span>
                <span className="text-xs text-muted-foreground">v0.1.0</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.path === "/"
                    ? location.pathname === "/"
                    : location.pathname.startsWith(item.path);

                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      onClick={() => navigate(item.path)}
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <item.icon className="size-4" />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          {FOOTER_ITEMS.map((item) => (
            <SidebarMenuItem key={item.path}>
              <SidebarMenuButton
                onClick={() => navigate(item.path)}
                isActive={location.pathname.startsWith(item.path)}
                tooltip={item.title}
              >
                <item.icon className="size-4" />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
