import {
  ArrowRight,
  CloudRainWind,
  Droplets,
  ExternalLink,
  Globe,
  History,
  MapPin,
  Mountain,
  Navigation,
  Network,
  Play,
  Search,
  Waves,
  Zap,
  AlertCircle,
} from "lucide-react"

const GITHUB_URL = "https://github.com/shalonjovan/Matsya"

interface HomePageProps {
  onLaunch: () => void
  onReplay2015: () => void
}

export default function HomePage({ onLaunch, onReplay2015 }: HomePageProps) {
  return (
    <div className="w-full" style={{ backgroundColor: "#070A0F", color: "#F1F5F9" }}>

      {/* ─────────────────────────── HERO ─────────────────────────── */}
      <section
        style={{
          minHeight: "calc(100vh - 64px)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          position: "relative",
          overflow: "hidden",
          borderBottom: "1px solid rgba(51,65,85,0.4)",
        }}
      >
        {/* Subtle grid */}
        <div
          aria-hidden
          style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.04) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        {/* Cyan glow — centered now */}
        <div
          aria-hidden
          style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            background:
              "radial-gradient(ellipse 70% 55% at 50% -5%, rgba(6,182,212,0.16) 0%, transparent 65%), radial-gradient(ellipse 50% 40% at 80% 90%, rgba(37,99,235,0.10) 0%, transparent 55%)",
          }}
        />

        <div style={{
          maxWidth: 800,
          margin: "0 auto",
          padding: "60px 40px 52px",
          width: "100%",
          position: "relative",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}>

          {/* ── Title ── */}
          <h1 style={{
            fontSize: "clamp(52px, 7vw, 80px)",
            fontWeight: 900,
            letterSpacing: "-0.04em",
            lineHeight: 1,
            background: "linear-gradient(135deg, #67E8F9 0%, #22D3EE 40%, #60A5FA 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            margin: 0,
          }}>
            MATSYA
          </h1>

          {/* ── Subtitle ── */}
          <p style={{
            fontSize: 15, fontWeight: 500, color: "#64748B",
            marginTop: 12, letterSpacing: "0.02em", lineHeight: 1.4,
          }}>
            Urban Flood Nowcasting &amp; Decision-Support System
          </p>

          {/* ── Context line ── */}
          <p style={{
            fontSize: 15, color: "#475569", marginTop: 28,
            maxWidth: 560, lineHeight: 1.8,
          }}>
            We already have systems that tell us{" "}
            <span style={{ color: "#93C5FD", fontWeight: 500 }}>how much rain is coming.</span>{" "}
            But for a disaster-management officer, that is not the most important question.
          </p>

          {/* ── The key question — left-accent style, no box ── */}
          <div style={{
            marginTop: 28,
            maxWidth: 640,
            width: "100%",
            textAlign: "left",
            paddingLeft: 20,
            borderLeft: "3px solid #22D3EE",
          }}>
            <p style={{
              fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em",
              textTransform: "uppercase", color: "#22D3EE", margin: "0 0 10px",
            }}>
              The real question
            </p>
            <p style={{
              fontSize: 22, fontWeight: 800, color: "#F1F5F9",
              lineHeight: 1.4, margin: 0,
            }}>
              Where is this water going to go?
            </p>
            <p style={{
              fontSize: 14, color: "#475569", marginTop: 10, lineHeight: 1.75,
            }}>
              Because the same rainfall can produce completely different outcomes in two parts of the same city —
              depending on its terrain, drains, lakes and built-up surface.
            </p>
          </div>

          {/* ── CTA buttons ── */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 36, justifyContent: "center" }}>
            <button
              type="button"
              onClick={onLaunch}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "13px 28px",
                background: "linear-gradient(135deg, #06B6D4, #3B82F6)",
                border: "none", borderRadius: 12,
                color: "#030712", fontWeight: 700, fontSize: 14,
                cursor: "pointer",
                boxShadow: "0 0 28px rgba(6,182,212,0.25)",
                letterSpacing: "0.01em",
              }}
            >
              <Play size={15} />
              Launch Console
              <ArrowRight size={15} />
            </button>
            <button
              type="button"
              onClick={onReplay2015}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "13px 28px",
                background: "transparent",
                border: "1px solid rgba(51,65,85,0.8)",
                borderRadius: 12,
                color: "#94A3B8", fontWeight: 600, fontSize: 14,
                cursor: "pointer",
              }}
            >
              <History size={15} style={{ color: "#22D3EE" }} />
              Dec 2015 Replay
            </button>
          </div>

          {/* ── Stats — clean, no boxes ── */}
          <div style={{
            marginTop: 48,
            paddingTop: 32,
            borderTop: "1px solid rgba(51,65,85,0.4)",
            width: "100%",
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 0,
          }}>
            {[
              { value: "30 m", label: "Terrain resolution", sub: "CartoDEM · ISRO" },
              { value: "10,257", label: "Stormwater drains", sub: "Mapped & modelled" },
              { value: "4,086", label: "Lakes & tanks", sub: "Storage & overflow" },
              { value: "3", label: "River networks", sub: "To the Bay of Bengal" },
            ].map((s, i) => (
              <div key={s.label} style={{
                textAlign: "left",
                borderLeft: i > 0 ? "1px solid rgba(51,65,85,0.35)" : "none",
                paddingLeft: i > 0 ? 28 : 0,
              }}>
                <div style={{
                  fontSize: 28, fontWeight: 900, fontFamily: "monospace",
                  color: "#22D3EE", lineHeight: 1,
                }}>{s.value}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#CBD5E1", marginTop: 6 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: "#334155", marginTop: 2, fontFamily: "monospace" }}>{s.sub}</div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* ─────────────────────────── THE WATER JOURNEY ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)", background: "rgba(10,14,22,0.8)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            HOW IT WORKS
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            The journey of water after it hits the ground
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 600, lineHeight: 1.75, marginBottom: 52 }}>
            A city is not an empty surface. It has buildings, roads, low-lying areas, storm-water drains, canals, lakes —
            and places where water can escape, or get trapped.
            MATSYA models every step of what happens after rainfall reaches the ground.
          </p>

          {/* Journey steps — horizontal pipeline */}
          <div style={{ display: "flex", gap: 0, alignItems: "stretch" }}>
            {[
              { icon: CloudRainWind, title: "Rainfall Input", note: "How much water is arriving" },
              { icon: Mountain, title: "Terrain & Surface", note: "Where the water flows — shape & elevation" },
              { icon: Network, title: "Drain Network", note: "What the infrastructure can carry" },
              { icon: Droplets, title: "Lakes & Rivers", note: "Storage, overflow and spill paths" },
              { icon: MapPin, title: "Flood-Risk Picture", note: "Where water collects, how deep, and when" },
            ].map(({ icon: Icon, title, note }, i, arr) => (
              <div key={title} style={{ display: "flex", alignItems: "center", flex: 1 }}>
                <div style={{
                  flex: 1,
                  background: "rgba(15,23,42,0.7)",
                  border: "1px solid rgba(51,65,85,0.8)",
                  borderRadius: 16,
                  padding: "28px 22px",
                  display: "flex", flexDirection: "column", gap: 14,
                  height: "100%",
                  boxSizing: "border-box",
                }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 12,
                    background: "rgba(6,182,212,0.12)",
                    border: "1px solid rgba(6,182,212,0.22)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#22D3EE", flexShrink: 0,
                  }}>
                    <Icon size={20} />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#F1F5F9" }}>{title}</div>
                    <div style={{ fontSize: 12, color: "#475569", marginTop: 5, lineHeight: 1.5 }}>{note}</div>
                  </div>
                </div>
                {i < arr.length - 1 && (
                  <div style={{ padding: "0 8px", color: "#1E3A5F", fontSize: 20, flexShrink: 0 }}>▸</div>
                )}
              </div>
            ))}
          </div>

          {/* Core idea callout */}
          <div style={{
            marginTop: 36, display: "flex", gap: 0,
            background: "rgba(15,23,42,0.7)",
            border: "1px solid rgba(51,65,85,0.8)",
            borderRadius: 16, overflow: "hidden",
          }}>
            <div style={{
              flex: 1, padding: "24px 28px",
              borderRight: "1px solid rgba(51,65,85,0.6)",
            }}>
              <p style={{ fontSize: 13, fontFamily: "monospace", color: "#22D3EE", marginBottom: 8, letterSpacing: "0.05em" }}>Rainfall tells us →</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9" }}>How much water is arriving.</p>
            </div>
            <div style={{ flex: 1, padding: "24px 28px" }}>
              <p style={{ fontSize: 13, fontFamily: "monospace", color: "#60A5FA", marginBottom: 8, letterSpacing: "0.05em" }}>The city tells us →</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9" }}>What happens to that water next.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── THE PROBLEM ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            01 — THE PROBLEM
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            Rain does not equal flood
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 640, lineHeight: 1.75, marginBottom: 48 }}>
            Flooding is not just the result of heavy rainfall. It is the result of the interaction between
            rainfall, surface, elevation, drainage and water bodies.
            Two neighbourhoods receiving the same rainfall can have completely different outcomes —
            because of how their drains, terrain and nearby water bodies behave together.
          </p>

          {/* Three root causes */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, marginBottom: 40 }}>
            {[
              {
                icon: Network,
                title: "A drain can carry only so much",
                body: "When the rate of inflow exceeds what the network can move, water backs up and spreads onto streets — even if the drain was recently cleared.",
              },
              {
                icon: Waves,
                title: "A lake can store only so much",
                body: "Once its storage capacity or outlet condition is exceeded, a lake stops absorbing water and starts contributing to flooding in surrounding areas.",
              },
              {
                icon: Mountain,
                title: "Low ground keeps collecting",
                body: "Where water arrives faster than it can leave, it continues accumulating — even after the rainfall eases. Terrain depressions dominate the outcome.",
              },
            ].map(({ icon: Icon, title, body }) => (
              <div key={title} style={{
                padding: "28px 24px",
                background: "rgba(15,23,42,0.7)",
                border: "1px solid rgba(51,65,85,0.8)",
                borderRadius: 16,
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: "rgba(6,182,212,0.1)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#22D3EE", marginBottom: 20,
                }}>
                  <Icon size={20} />
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9", marginBottom: 10 }}>{title}</div>
                <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{body}</div>
              </div>
            ))}
          </div>

          {/* What existing systems miss */}
          <div style={{
            padding: "24px 28px",
            background: "rgba(6,182,212,0.06)",
            border: "1px solid rgba(6,182,212,0.2)",
            borderRadius: 16,
            display: "flex", gap: 16, alignItems: "flex-start",
          }}>
            <AlertCircle size={20} style={{ color: "#22D3EE", flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ fontSize: 15, fontWeight: 600, color: "#CBD5E1", marginBottom: 6 }}>
                What existing systems miss
              </p>
              <p style={{ fontSize: 14, color: "#64748B", lineHeight: 1.75 }}>
                Weather models and rainfall forecasts give city-scale totals. They cannot resolve the micro-topology
                of streets, drain networks and waterbodies that determines which neighbourhood floods and which stays dry.
                Emergency teams cannot act on <em style={{ color: "#93C5FD" }}>"it is raining heavily"</em> —
                they need to know <strong style={{ color: "#CBD5E1" }}>where to send people, which roads may be unsafe, and where to monitor first.</strong>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── OUR APPROACH ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)", background: "rgba(10,14,22,0.8)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            02 — OUR APPROACH
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            Couple the physics. See the complete picture.
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 620, lineHeight: 1.75, marginBottom: 48 }}>
            MATSYA treats the city as a connected hydrological system.
            Instead of looking at rainfall, drains and waterbodies separately, we bring them together —
            so the simulation reflects what actually happens on the ground during a storm.
          </p>

          {/* 3 approach cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, marginBottom: 48 }}>
            {[
              {
                icon: Network,
                title: "Coupled Hydrodynamics",
                body: "Surface flow, drain network capacity and waterbody storage are solved simultaneously. Water moves through each stage and the output reflects their combined interaction.",
              },
              {
                icon: Zap,
                title: "Nowcast-Ready",
                body: "Designed to ingest near-real-time rainfall grids so the flood-risk picture updates as the storm evolves — not just after it has passed.",
              },
              {
                icon: Globe,
                title: "City-Agnostic Design",
                body: "The physics engine is city-independent. For another city, we change the input data — its DEM, drainage network, waterbodies and roads. The reasoning stays the same.",
              },
            ].map(({ icon: Icon, title, body }) => (
              <div key={title} style={{
                padding: "28px 24px",
                background: "rgba(15,23,42,0.7)",
                border: "1px solid rgba(51,65,85,0.8)",
                borderRadius: 16,
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: "rgba(6,182,212,0.1)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#22D3EE", marginBottom: 20,
                }}>
                  <Icon size={20} />
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9", marginBottom: 10 }}>{title}</div>
                <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{body}</div>
              </div>
            ))}
          </div>

          {/* Pipeline chips */}
          <div>
            <p style={{ fontSize: 12, fontFamily: "monospace", color: "#334155", letterSpacing: "0.1em", marginBottom: 14, textTransform: "uppercase" }}>
              Computation pipeline
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
              {["Rainfall", "DEM Routing", "Drain Network", "Lake Storage", "River Channels", "Risk Output"].map((step, i, arr) => (
                <div key={step} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    padding: "7px 16px",
                    background: "rgba(15,23,42,0.9)",
                    border: "1px solid rgba(51,65,85,0.8)",
                    borderRadius: 8, fontSize: 12,
                    fontFamily: "monospace", color: "#93C5FD",
                  }}>
                    {step}
                  </span>
                  {i < arr.length - 1 && <span style={{ color: "#1E3A5F", fontSize: 16 }}>▸</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── WHAT IT ENABLES ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            03 — DECISION SUPPORT
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            From rainfall warning to action on the ground
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 620, lineHeight: 1.75, marginBottom: 48 }}>
            Once we know where water is likely to accumulate, the output becomes actionable.
            Instead of <em>"this region may receive heavy rainfall,"</em>{" "}
            the system helps authorities understand which areas are at higher risk, which roads may be affected,
            and where attention is needed first.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {[
              {
                icon: MapPin,
                title: "Which roads may be affected?",
                body: "Road segments are checked against simulated water-depth conditions. Problem corridors are identified before the peak arrives.",
              },
              {
                icon: Navigation,
                title: "Should an emergency route avoid a flooded section?",
                body: "The prototype can point to a safer path — supporting emergency logistics, municipal teams and daily commuters.",
              },
              {
                icon: Search,
                title: "Which locations need priority monitoring?",
                body: "Areas ranked by expected water accumulation so disaster-management teams can deploy resources where they matter most.",
              },
            ].map(({ icon: Icon, title, body }) => (
              <div key={title} style={{
                padding: "28px 24px",
                background: "rgba(15,23,42,0.7)",
                border: "1px solid rgba(51,65,85,0.8)",
                borderRadius: 16,
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 12,
                  background: "rgba(6,182,212,0.1)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#22D3EE", marginBottom: 20,
                }}>
                  <Icon size={20} />
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9", marginBottom: 10 }}>{title}</div>
                <div style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>{body}</div>
              </div>
            ))}
          </div>

          <p style={{
            marginTop: 28, fontSize: 13, fontFamily: "monospace",
            color: "#334155", letterSpacing: "0.04em",
          }}>
            Decision-support prototype · model output, verify on the ground · not a replacement for official emergency systems
          </p>
        </div>
      </section>

      {/* ─────────────────────────── DATA FOUNDATION ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)", background: "rgba(10,14,22,0.8)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            04 — DATA FOUNDATION
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            Real infrastructure data. Real urban environment.
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 600, lineHeight: 1.75, marginBottom: 48 }}>
            We started with Chennai because it gives us a meaningful prototype environment —
            dense development, drainage infrastructure, low-lying regions and multiple water bodies.
            Every layer of data is integrated into one coherent model.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 40 }}>
            {[
              { label: "CartoDEM 30 m", detail: "ISRO elevation model — terrain & surface routing" },
              { label: "10,257 drain geometries", detail: "Stormwater network — capacity & routing" },
              { label: "4,086 waterbodies", detail: "Lakes, tanks, ponds — storage & overflow" },
              { label: "876 river reaches", detail: "Adyar, Cooum, Buckingham Canal → sea" },
              { label: "IMD rainfall grids", detail: "Observed & forecast precipitation inputs" },
              { label: "OpenStreetMap roads", detail: "Risk overlay and safe-route computation" },
            ].map(({ label, detail }) => (
              <div key={label} style={{
                display: "flex", alignItems: "flex-start", gap: 14,
                padding: "20px 20px",
                background: "rgba(15,23,42,0.7)",
                border: "1px solid rgba(51,65,85,0.8)",
                borderRadius: 14,
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: "#22D3EE", flexShrink: 0, marginTop: 5,
                }} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#CBD5E1" }}>{label}</div>
                  <div style={{ fontSize: 12, color: "#475569", marginTop: 3, lineHeight: 1.5 }}>{detail}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Key finding */}
          <div style={{
            padding: "28px 32px",
            background: "rgba(6,182,212,0.06)",
            border: "1px solid rgba(6,182,212,0.2)",
            borderRadius: 16,
          }}>
            <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.15em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 10 }}>
              Key simulation finding
            </p>
            <p style={{ fontSize: 19, fontWeight: 700, color: "#F1F5F9", lineHeight: 1.5 }}>
              Even with <span style={{ color: "#22D3EE" }}>infinite drain capacity,</span> 10.1% of the domain still floods.
            </p>
            <p style={{ fontSize: 14, color: "#64748B", marginTop: 10, lineHeight: 1.75, maxWidth: 600 }}>
              Terrain depressions dominate — proving that drainage upgrades alone cannot solve urban flooding.
              The land surface and drainage infrastructure must be modelled together.
              That coupling is the heart of this project.
            </p>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── SCALABILITY ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px" }}>

          <p style={{ fontSize: 11, fontFamily: "monospace", letterSpacing: "0.2em", textTransform: "uppercase", color: "#22D3EE", marginBottom: 16 }}>
            05 — SCALABILITY
          </p>
          <h2 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em", color: "#F1F5F9", marginBottom: 12 }}>
            Built on one city. Not limited to one city.
          </h2>
          <p style={{ fontSize: 15, color: "#64748B", maxWidth: 640, lineHeight: 1.75, marginBottom: 48 }}>
            MATSYA is not designed around the name "Chennai."
            The underlying idea is city-independent. For another city, we change the input data —
            its elevation, drainage network, waterbodies, roads and rainfall inputs.
            The physics reasoning stays exactly the same.
          </p>

          <div style={{
            padding: "32px 36px",
            background: "rgba(15,23,42,0.7)",
            border: "1px solid rgba(51,65,85,0.8)",
            borderRadius: 16,
            display: "flex", alignItems: "center", gap: 32, flexWrap: "wrap",
          }}>
            <div style={{ flex: "0 0 auto" }}>
              <Globe size={36} style={{ color: "#22D3EE" }} />
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <p style={{ fontSize: 15, fontWeight: 600, color: "#CBD5E1", marginBottom: 8 }}>
                Applicable wherever local data is available
              </p>
              <p style={{ fontSize: 13, color: "#64748B", lineHeight: 1.7 }}>
                Any metropolitan region with available DEM, stormwater network, waterbody and road data can be modelled
                using the same approach. Urban flooding is not a Chennai problem — it is a national challenge.
              </p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {["Mumbai", "Bengaluru", "Hyderabad", "Kolkata", "Delhi"].map((c) => (
                <span key={c} style={{
                  padding: "6px 16px", borderRadius: 999,
                  background: "rgba(6,182,212,0.08)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  fontSize: 13, fontFamily: "monospace", color: "#93C5FD",
                }}>{c}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── FINAL CTA ─────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(51,65,85,0.5)", background: "rgba(10,14,22,0.8)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 40px", textAlign: "center" }}>

          <h2 style={{
            fontSize: 34, fontWeight: 900, letterSpacing: "-0.02em",
            color: "#F1F5F9", lineHeight: 1.45, maxWidth: 680, margin: "0 auto 16px",
          }}>
            Today, authorities have information about what is happening{" "}
            <span style={{ color: "#93C5FD" }}>in the sky.</span>
          </h2>
          <p style={{
            fontSize: 22, fontWeight: 700, color: "#22D3EE",
            maxWidth: 680, margin: "0 auto 40px", lineHeight: 1.5,
          }}>
            MATSYA adds the missing layer — what is going to happen on the ground.
          </p>

          <p style={{ fontSize: 16, color: "#64748B", maxWidth: 520, margin: "0 auto 44px", lineHeight: 1.75 }}>
            Knowing that rain is coming is useful.{" "}
            <strong style={{ color: "#CBD5E1" }}>Knowing where the water is going can help turn information into action.</strong>
          </p>

          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={onLaunch}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "14px 30px",
                background: "linear-gradient(135deg, #06B6D4, #3B82F6)",
                border: "none", borderRadius: 12,
                color: "#030712", fontWeight: 700, fontSize: 15,
                cursor: "pointer",
                boxShadow: "0 0 32px rgba(6,182,212,0.3)",
              }}
            >
              <Play size={18} />
              Open the Console
              <ArrowRight size={18} />
            </button>
            <button
              type="button"
              onClick={onReplay2015}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "14px 30px",
                background: "rgba(15,23,42,0.9)",
                border: "1px solid rgba(51,65,85,0.9)",
                borderRadius: 12,
                color: "#CBD5E1", fontWeight: 600, fontSize: 15,
                cursor: "pointer",
              }}
            >
              <History size={18} style={{ color: "#22D3EE" }} />
              Replay the 2015 Storm
            </button>
          </div>
        </div>
      </section>

      {/* ─────────────────────────── FOOTER ─────────────────────────── */}
      <footer>
        <div style={{
          maxWidth: 1100, margin: "0 auto", padding: "28px 40px",
          display: "flex", flexWrap: "wrap", alignItems: "center",
          justifyContent: "space-between", gap: 16,
          fontSize: 11, fontFamily: "monospace", color: "#334155",
          borderTop: "1px solid rgba(51,65,85,0.4)",
        }}>
          <span>Team Blastorz · P74 · SIH 2026 · PS SIH26085 · SSN College of Engineering · MoES / NCMRWF</span>
          <span>Decision-support prototype · verify on the ground</span>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            style={{ display: "flex", alignItems: "center", gap: 6, color: "#475569", textDecoration: "none" }}
          >
            <ExternalLink size={13} />
            GitHub
          </a>
        </div>
      </footer>

    </div>
  )
}
