# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT
"""
Cruse Theme Agent Constants
Defines constants and templates for generating CRUSE themes,
including css-doodle patterns, Trianglify patterns, CSS gradients, and color palettes.
"""

# css-doodle pattern templates with comprehensive configuration options
CSS_DOODLE_TEMPLATES = {
    "neural_network": {
        "type": "css-doodle",
        "grid": "14x10",
        "seed": None,  # Will be set to agent-specific seed
        "rules": """
:doodle {
  @grid: 14x10 / 100vmax;
  background: var(--bg);
}
:after {
  content: '';
  @size: 120% 120%;
  @place: center;
  background:
    radial-gradient(circle at 0 0, var(--accent-soft), transparent 55%),
    radial-gradient(circle at 100% 0, var(--accent), transparent 55%),
    radial-gradient(circle at 50% 100%, var(--accent-soft), transparent 60%);
  opacity: @rand(.2, .6);
  filter: blur(@rand(12px, 28px));
}
        """,
        "vars": {"--bg": "#0f172a", "--accent": "#3b82f6", "--accent-soft": "#60a5fa"},
        "description": "Neural network-inspired radial gradients - ideal for AI, technology, data science",
        "best_for": ["AI", "technology", "data", "machine_learning", "analytics", "innovation"],
    },
    "geometric_tech": {
        "type": "css-doodle",
        "grid": "10",
        "seed": None,
        "rules": """
:doodle {
  @grid: 10 / 100vmax;
  background: var(--bg);
}
background: @p(
  var(--accent-dark),
  var(--accent),
  var(--accent-soft),
  transparent
);
opacity: @rand(.3, .9);
transform: scale(@rand(.8, 1.2)) rotate(@rand(360deg));
        """,
        "vars": {"--bg": "#020617", "--accent": "#0ea5e9", "--accent-dark": "#0c4a6e", "--accent-soft": "#38bdf8"},
        "description": "Geometric shapes with random transforms - modern tech aesthetic",
        "best_for": ["technology", "software", "business", "corporate", "professional"],
    },
    "organic_dots": {
        "type": "css-doodle",
        "grid": "16x12",
        "seed": None,
        "rules": """
:doodle {
  @grid: 16x12 / 100vmax;
  background: var(--bg);
}
:after {
  content: '';
  background: var(--accent);
  @size: @rand(2px, 8px);
  @place: @rand(0, 100)% @rand(0, 100)%;
  border-radius: 50%;
  opacity: @rand(.2, .8);
  animation: float @rand(3s, 8s) ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(@rand(-20px, 20px)); }
}
        """,
        "vars": {"--bg": "#134e4a", "--accent": "#5eead4"},
        "description": "Floating organic dots - calm, healthcare, wellness aesthetic",
        "best_for": ["healthcare", "wellness", "biology", "organic", "calm", "medical"],
    },
    "financial_grid": {
        "type": "css-doodle",
        "grid": "12x8",
        "seed": None,
        "rules": """
:doodle {
  @grid: 12x8 / 100vmax;
  background: var(--bg);
}
border: 1px solid var(--accent);
opacity: @rand(.1, .4);
background: @p(
  linear-gradient(var(--accent-dark), transparent),
  linear-gradient(to right, var(--accent), transparent),
  transparent
);
transform: translateY(@rand(-5px, 5px));
        """,
        "vars": {"--bg": "#14532d", "--accent": "#22c55e", "--accent-dark": "#15803d"},
        "description": "Grid-based financial chart aesthetic - professional, growth-oriented",
        "best_for": ["finance", "banking", "investment", "trading", "analytics", "business"],
    },
    "creative_chaos": {
        "type": "css-doodle",
        "grid": "8",
        "seed": None,
        "rules": """
:doodle {
  @grid: 8 / 100vmax;
  background: var(--bg);
}
@shape: @p(circle, triangle, rhombus, pentagon, hexagon);
background: @p(var(--color1), var(--color2), var(--color3));
opacity: @rand(.3, .7);
transform:
  scale(@rand(.5, 1.5))
  rotate(@rand(360deg))
  translate(@rand(-20%, 20%), @rand(-20%, 20%));
        """,
        "vars": {"--bg": "#1a0a1e", "--color1": "#9c27b0", "--color2": "#e91e63", "--color3": "#f97316"},
        "description": "Creative chaotic shapes - vibrant, artistic, dynamic",
        "best_for": ["creative", "design", "art", "media", "entertainment", "marketing"],
    },
    "educational_blocks": {
        "type": "css-doodle",
        "grid": "10x8",
        "seed": None,
        "rules": """
:doodle {
  @grid: 10x8 / 100vmax;
  background: var(--bg);
}
@shape: square;
background: @p(var(--primary), var(--secondary), transparent);
opacity: @rand(.2, .6);
border: @rand(1px, 3px) solid var(--accent);
transform: rotate(@rand(0deg, 15deg));
        """,
        "vars": {"--bg": "#2e1a0a", "--primary": "#ff6f00", "--secondary": "#e65100", "--accent": "#ffb74d"},
        "description": "Building blocks pattern - educational, structured, warm",
        "best_for": ["education", "learning", "training", "academic", "teaching"],
    },
    "aviation_flow": {
        "type": "css-doodle",
        "grid": "20x5",
        "seed": None,
        "rules": """
:doodle {
  @grid: 20x5 / 100vmax;
  background: var(--bg);
}
:after {
  content: '';
  @size: 100% 2px;
  background: linear-gradient(
    to right,
    transparent,
    var(--accent),
    transparent
  );
  opacity: @rand(.2, .8);
  animation: flow @rand(5s, 15s) linear infinite;
}
@keyframes flow {
  from { transform: translateX(-100%); }
  to { transform: translateX(100%); }
}
        """,
        "vars": {"--bg": "#0c4a6e", "--accent": "#38bdf8"},
        "description": "Flowing lines like flight paths - aviation, travel, movement",
        "best_for": ["aviation", "travel", "logistics", "transportation", "journey"],
    },
    "minimal_professional": {
        "type": "css-doodle",
        "grid": "6",
        "seed": None,
        "rules": """
:doodle {
  @grid: 6 / 100vmax;
  background: var(--bg);
}
@shape: square;
background: var(--accent);
opacity: @rand(.05, .15);
transform: scale(@rand(.8, 1.2));
        """,
        "vars": {"--bg": "#0f172a", "--accent": "#64b5f6"},
        "description": "Minimal, subtle squares - professional, clean, understated",
        "best_for": ["legal", "consulting", "professional", "corporate", "formal"],
    },
    "data_waves": {
        "type": "css-doodle",
        "grid": "30x10",
        "seed": None,
        "rules": """
:doodle {
  @grid: 30x10 / 100vmax;
  background: var(--bg);
}
:after {
  content: '';
  @size: 100% 3px;
  background: var(--accent);
  opacity: @rand(.2, .6);
  transform: translateY(@rand(-50%, 50%));
}
        """,
        "vars": {"--bg": "#020617", "--accent": "#06b6d4"},
        "description": "Data visualization waves - analytics, insights, metrics",
        "best_for": ["analytics", "data", "insights", "metrics", "reporting", "dashboards"],
    },
    "elegant_circles": {
        "type": "css-doodle",
        "grid": "12",
        "seed": None,
        "rules": """
:doodle {
  @grid: 12 / 100vmax;
  background: var(--bg);
}
@shape: circle;
border: @rand(1px, 2px) solid var(--accent);
opacity: @rand(.1, .3);
@size: @rand(30%, 80%);
        """,
        "vars": {"--bg": "#1e1e1e", "--accent": "#bb86fc"},
        "description": "Elegant overlapping circles - sophisticated, modern, timeless",
        "best_for": ["luxury", "premium", "sophisticated", "modern", "universal"],
    },
    # Dynamic animated particle system pattern
    "reactive_particles": {
        "type": "css-doodle",
        "grid": "25x20",
        "seed": None,
        "rules": """
  :doodle {
    @grid: 25x20 / 100vmax;
    background: var(--bg);
  }
  background: @pick(var(--c1), var(--c2), var(--c3));
  @size: @rand(3px, 12px);
  border-radius: 50%;
  transform:
    translateX(@calc(sin(@t(*.001) + @i) * 100)px)
    translateY(@calc(cos(@t(*.001) + @i * 1.5) * 80)px)
    scale(@calc(abs(sin(@t(*.002) + @i)) * .5 + .5));
  opacity: @calc(abs(cos(@t(*.003) + @i)) * .6 + .4);
  filter: blur(@rand(0, 1)px);
      """,
        "vars": {"--bg": "#020617", "--c1": "#3b82f6", "--c2": "#8b5cf6", "--c3": "#06b6d4"},
        "description": "Real-time animated particle system - AI/tech/dynamic",
        "best_for": ["AI", "technology", "dynamic", "innovation"],
    },
    # Perlin noise based organic flow pattern
    "organic_flow": {
        "type": "css-doodle",
        "grid": "15x10",
        "seed": None,
        "rules": """
  :doodle {
    @grid: 15x10 / 100vmax;
    background: var(--bg);
  }
  @shape: circle;
  background: hsl(@rn(var(--hue-min), var(--hue-max), frequency: .5), 70%, 65%);
  @size: @rn(20px, 50px, frequency: .3);
  transform:
    translateX(@rn(-50, 50, octave: 2)px)
    translateY(@rn(-50, 50, octave: 2)px)
    rotate(@rn(0, 360, frequency: .5)deg)
    scale(@rn(.7, 1.4, octave: 3));
  opacity: @rn(.2, .7, frequency: .4);
  filter: blur(@rn(1, 4)px);
      """,
        "vars": {"--bg": "#0f172a", "--hue-min": "200", "--hue-max": "280"},
        "description": "Smooth organic flow with Perlin noise - natural/healthcare/calm",
        "best_for": ["healthcare", "wellness", "organic", "nature"],
    },
    # Mouse-interactive responsive pattern
    "interactive_constellation": {
        "type": "css-doodle",
        "grid": "25x20",
        "seed": None,
        "rules": """
  :doodle {
    @grid: 25x20 / 100vmax;
    background: var(--bg);
  }
  background: white;
  @size: @rand(2px, 8px);
  border-radius: 50%;
  box-shadow: 0 0 @rand(10px, 30px) var(--glow);
  transform:
    translateX(@calc((@ux - 50) * @dx * 3)px)
    translateY(@calc((@uy - 50) * @dy * 3)px)
    scale(@calc(1 + sqrt(abs(@dx * @dx + @dy * @dy)) * .2));
  opacity: @rand(.4, 1);
  transition: transform .5s ease-out;
  animation: twinkle @rand(2s, 5s) @rand(0s, 3s) infinite;

  @keyframes twinkle {
    0%, 100% { opacity: @rand(.3, .7); }
    50% { opacity: 1; }
  }
      """,
        "vars": {"--bg": "#000814", "--glow": "rgba(147, 197, 253, 0.8)"},
        "description": "Mouse-reactive star field - interactive/space/technology",
        "best_for": ["technology", "astronomy", "interactive", "innovation"],
    },
    # Advannced Shapes
    "parametric_flowers": {
        "type": "css-doodle",
        "grid": "10",
        "seed": None,
        "rules": """
  :doodle {
    @grid: 10 / 100vmax;
    background: var(--bg);
  }
  @shape:
    split: 180;
    r: @pick(cos(3t), cos(5t), cos(7t), sin(3t)^2 + cos(3t)^2);
    rotate: @rand(360);
    scale: @rand(.4, .8);
  background: @pick(var(--c1), var(--c2), var(--c3));
  opacity: @rand(.3, .6);
  transform:
    translate(@rand(-30%, 30%), @rand(-30%, 30%))
    rotate(@rand(360deg));
  filter: blur(@rand(1, 3)px);
      """,
        "vars": {"--bg": "#fef3c7", "--c1": "#fbbf24", "--c2": "#f59e0b", "--c3": "#d97706"},
        "description": "Mathematical flower patterns - creative/organic/nature",
        "best_for": ["creative", "nature", "organic", "wellness"],
    },
    # Easing and smooth gradations
    "gradient_wave": {
        "type": "css-doodle",
        "grid": "1x30",
        "seed": None,
        "rules": """
  :doodle {
    @grid: 1x30 / 100vmax;
    background: var(--bg);
  }
  background: linear-gradient(90deg,
    hsl(@iI(*360), 70%, 60%),
    hsl(@iI(*360, +40), 70%, 70%)
  );
  height: @rand(3%, 8%);
  transform:
    translateY(@calc(sin(@t(*.003) + @i * .3) * 50)px)
    scaleX(@calc(1 + abs(sin(@t(*.002) + @i * .2)) * .3));
  opacity: @calc(abs(cos(@t(*.002) + @i * .4)) * .4 + .6);
  border-radius: 50%;
      """,
        "vars": {"--bg": "#020617"},
        "description": "Animated wave with easing - data/analytics/flow",
        "best_for": ["analytics", "data", "flow", "metrics"],
    },
}

# Note: Trianglify templates removed - use CSS Gradients for static themes instead

# CSS Gradient templates for lightweight backgrounds
GRADIENT_TEMPLATES = {
    "linear_default": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [{"color": "#0f172a", "stop": "0%"}, {"color": "#1e293b", "stop": "100%"}],
        "description": "Simple linear gradient (diagonal)",
    },
    "linear_business": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [
            {"color": "#1e3a8a", "stop": "0%"},
            {"color": "#3b82f6", "stop": "50%"},
            {"color": "#0ea5e9", "stop": "100%"},
        ],
        "description": "Professional blue gradient",
    },
    "linear_financial": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [
            {"color": "#14532d", "stop": "0%"},
            {"color": "#22c55e", "stop": "50%"},
            {"color": "#4ade80", "stop": "100%"},
        ],
        "description": "Financial green gradient",
    },
    "linear_healthcare": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [
            {"color": "#134e4a", "stop": "0%"},
            {"color": "#14b8a6", "stop": "50%"},
            {"color": "#5eead4", "stop": "100%"},
        ],
        "description": "Healthcare teal gradient",
    },
    "radial_spotlight": {
        "type": "gradient",
        "mode": "radial",
        "shape": "circle",
        "colors": [
            {"color": "#3b82f6", "stop": "0%"},
            {"color": "#1e40af", "stop": "50%"},
            {"color": "#0f172a", "stop": "100%"},
        ],
        "description": "Radial gradient with center spotlight effect",
    },
    "conic_creative": {
        "type": "gradient",
        "mode": "conic",
        "colors": [
            {"color": "#8b5cf6", "stop": "0%"},
            {"color": "#ec4899", "stop": "25%"},
            {"color": "#f97316", "stop": "50%"},
            {"color": "#eab308", "stop": "75%"},
            {"color": "#8b5cf6", "stop": "100%"},
        ],
        "description": "Conic gradient for creative, colorful effects",
    },
    "linear_sunset": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [
            {"color": "#7f1d1d", "stop": "0%"},
            {"color": "#dc2626", "stop": "30%"},
            {"color": "#f97316", "stop": "60%"},
            {"color": "#fbbf24", "stop": "100%"},
        ],
        "description": "Warm sunset gradient (red-orange-yellow)",
    },
    "linear_ocean": {
        "type": "gradient",
        "mode": "linear",
        "angle": "135deg",
        "colors": [
            {"color": "#0c4a6e", "stop": "0%"},
            {"color": "#0891b2", "stop": "45%"},
            {"color": "#22d3ee", "stop": "100%"},
        ],
        "description": "Ocean blue gradient for travel/water themes",
    },
}

# Domain-specific color palettes with psychological context
COLOR_PALETTES = {
    "business_corporate": {
        "primary": "#1976d2",  # Professional blue
        "secondary": "#0d47a1",  # Deep blue
        "accent": "#64b5f6",  # Light blue
        "background_light": "#e3f2fd",
        "background_dark": "#0d1b2a",
        "description": "Trust, professionalism, stability",
        "psychology": "Blue conveys trust, security, and corporate professionalism",
        "use_cases": ["business", "corporate", "consulting", "enterprise"],
    },
    "financial_banking": {
        "primary": "#2e7d32",  # Money green
        "secondary": "#1b5e20",  # Deep green
        "accent": "#66bb6a",  # Light green
        "background_light": "#e8f5e9",
        "background_dark": "#1a2e1a",
        "description": "Growth, prosperity, financial success",
        "psychology": "Green represents growth, money, and financial stability",
        "use_cases": ["finance", "banking", "investment", "portfolio"],
    },
    "healthcare_wellness": {
        "primary": "#00897b",  # Medical teal
        "secondary": "#004d40",  # Deep teal
        "accent": "#4db6ac",  # Light teal
        "background_light": "#e0f2f1",
        "background_dark": "#0a1f1c",
        "description": "Calm, healing, trust",
        "psychology": "Teal combines blue's trust with green's healing properties",
        "use_cases": ["healthcare", "medical", "wellness", "therapy"],
    },
    "education_learning": {
        "primary": "#ff6f00",  # Energetic orange
        "secondary": "#e65100",  # Deep orange
        "accent": "#ffb74d",  # Light orange
        "background_light": "#fff3e0",
        "background_dark": "#2e1a0a",
        "description": "Enthusiasm, creativity, warmth",
        "psychology": "Orange stimulates mental activity and encourages learning",
        "use_cases": ["education", "learning", "training", "academic"],
    },
    "technology_innovation": {
        "primary": "#00bcd4",  # Tech cyan
        "secondary": "#0097a7",  # Deep cyan
        "accent": "#4dd0e1",  # Light cyan
        "tertiary": "#7b1fa2",  # Tech purple
        "background_light": "#e0f7fa",
        "background_dark": "#0a1929",
        "description": "Innovation, modernity, cutting-edge",
        "psychology": "Cyan/purple conveys futuristic, tech-forward thinking",
        "use_cases": ["technology", "AI", "software", "innovation"],
    },
    "creative_design": {
        "primary": "#9c27b0",  # Creative purple
        "secondary": "#6a1b9a",  # Deep purple
        "accent": "#ba68c8",  # Light purple
        "tertiary": "#e91e63",  # Pink accent
        "background_light": "#f3e5f5",
        "background_dark": "#1a0a1e",
        "description": "Creativity, luxury, imagination",
        "psychology": "Purple represents creativity, wisdom, and artistic expression",
        "use_cases": ["creative", "design", "art", "media", "entertainment"],
    },
    "retail_ecommerce": {
        "primary": "#d32f2f",  # Bold red
        "secondary": "#c62828",  # Deep red
        "accent": "#ef5350",  # Light red
        "background_light": "#ffebee",
        "background_dark": "#2e0a0a",
        "description": "Energy, urgency, excitement",
        "psychology": "Red grabs attention and creates sense of urgency",
        "use_cases": ["retail", "ecommerce", "sales", "marketing"],
    },
    "legal_professional": {
        "primary": "#0d47a1",  # Deep authoritative blue
        "secondary": "#01579b",  # Navy blue
        "accent": "#42a5f5",  # Light blue
        "background_light": "#e1f5fe",
        "background_dark": "#0a1929",
        "description": "Authority, trust, professionalism",
        "psychology": "Deep blue conveys authority, expertise, and trustworthiness",
        "use_cases": ["legal", "law", "compliance", "government"],
    },
    "travel_aviation": {
        "primary": "#0288d1",  # Sky blue
        "secondary": "#01579b",  # Deep blue
        "accent": "#4fc3f7",  # Light blue
        "tertiary": "#ffa726",  # Sunset orange
        "background_light": "#e1f5fe",
        "background_dark": "#0a1929",
        "description": "Freedom, exploration, adventure",
        "psychology": "Sky blue evokes open skies and freedom of travel",
        "use_cases": ["travel", "aviation", "tourism", "hospitality"],
    },
    "dark_mode_universal": {
        "primary": "#bb86fc",  # Material purple
        "secondary": "#3700b3",  # Deep purple
        "accent": "#03dac6",  # Teal accent
        "background_light": "#1e1e1e",
        "background_dark": "#121212",
        "description": "Modern dark theme for any domain",
        "psychology": "Reduces eye strain, modern aesthetic",
        "use_cases": ["universal", "dark_mode", "night_mode"],
    },
}
