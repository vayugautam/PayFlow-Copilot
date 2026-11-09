import { Construction } from "lucide-react";
import { Card } from "../../components/ui";

export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return <div className="placeholder-page"><Card><div className="placeholder-icon"><Construction size={22} /></div><span className="eyebrow">Phase 6B</span><h2>{title}</h2><p className="muted">{description}</p><span className="planned">Planned module · No fake interactions are shown</span></Card></div>;
}
