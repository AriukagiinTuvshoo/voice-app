import { SettingsPanel } from "@/components/AppShell";

export default function Settings() {
  return (
    <section className="page">
      <h1>Тохиргоо</h1>
      <p>Бичлэг, микрофон, дүрэм шалгалт болон харагдах байдлын тохиргоо.</p>
      <SettingsPanel />
    </section>
  );
}
