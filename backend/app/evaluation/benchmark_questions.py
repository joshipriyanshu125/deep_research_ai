"""
Day 60 — 100 Evaluation Benchmark Questions

Curated across 10 research domains (10 questions each):
  1. Technology & AI
  2. Climate & Environment
  3. Healthcare & Medicine
  4. Economics & Finance
  5. Energy & Clean Tech
  6. Geopolitics & Policy
  7. Space & Science
  8. Business & Markets
  9. Education & Society
  10. Cybersecurity

Usage::

    from app.evaluation.benchmark_questions import BENCHMARK_QUESTIONS, load_benchmark
    from app.evaluation.framework import evaluation_framework

    evaluation_framework.add_questions(BENCHMARK_QUESTIONS)
    report = await evaluation_framework.run_benchmark(my_research_fn)
"""

from app.evaluation.framework import BenchmarkQuestion

BENCHMARK_QUESTIONS: list[BenchmarkQuestion] = [

    # -----------------------------------------------------------------------
    # Domain 1 — Technology & AI (q001–q010)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q001",
        question="What are the key architectural differences between GPT-4 and LLaMA 3?",
        expected_keywords=["transformer", "attention", "parameters", "training", "architecture"],
        expected_sources=["arxiv.org", "openai.com", "meta.com"],
        topic="Technology & AI", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q002",
        question="How does retrieval-augmented generation (RAG) improve LLM accuracy?",
        expected_keywords=["retrieval", "vector", "embedding", "hallucination", "context"],
        expected_sources=["arxiv.org"],
        topic="Technology & AI", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q003",
        question="What is the current state of quantum computing hardware in 2025?",
        expected_keywords=["qubit", "error correction", "IBM", "Google", "coherence"],
        expected_sources=["nature.com", "arxiv.org"],
        topic="Technology & AI", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q004",
        question="What are the main risks of deploying autonomous AI agents in production?",
        expected_keywords=["safety", "alignment", "hallucination", "tool use", "sandboxing"],
        topic="Technology & AI", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q005",
        question="How does speculative decoding accelerate LLM inference?",
        expected_keywords=["draft model", "tokens", "latency", "throughput", "speculation"],
        expected_sources=["arxiv.org"],
        topic="Technology & AI", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q006",
        question="What are the leading vector database solutions and their trade-offs?",
        expected_keywords=["Pinecone", "Weaviate", "Chroma", "FAISS", "similarity"],
        topic="Technology & AI", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q007",
        question="How is multimodal AI being used in medical imaging?",
        expected_keywords=["vision", "radiology", "diagnosis", "CNN", "foundation model"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov", "nature.com"],
        topic="Technology & AI", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q008",
        question="What is the role of RLHF in aligning large language models?",
        expected_keywords=["reinforcement", "human feedback", "reward model", "preference", "PPO"],
        expected_sources=["arxiv.org", "openai.com"],
        topic="Technology & AI", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q009",
        question="What are the main open-source alternatives to GPT-4?",
        expected_keywords=["Mistral", "LLaMA", "Falcon", "open-source", "benchmark"],
        topic="Technology & AI", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q010",
        question="How does mixture-of-experts (MoE) architecture improve model efficiency?",
        expected_keywords=["experts", "routing", "sparse", "parameters", "Mixtral"],
        expected_sources=["arxiv.org"],
        topic="Technology & AI", difficulty="hard",
    ),

    # -----------------------------------------------------------------------
    # Domain 2 — Climate & Environment (q011–q020)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q011",
        question="What are the primary drivers of Arctic sea ice loss?",
        expected_keywords=["temperature", "albedo", "methane", "permafrost", "feedback"],
        expected_sources=["nature.com", "ipcc.ch"],
        topic="Climate & Environment", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q012",
        question="How do carbon capture and storage (CCS) technologies work?",
        expected_keywords=["CO2", "sequestration", "geological", "capture", "storage"],
        expected_sources=["iea.org"],
        topic="Climate & Environment", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q013",
        question="What is the current global average temperature anomaly relative to pre-industrial levels?",
        expected_keywords=["1.5", "2.0", "degrees", "baseline", "anomaly"],
        expected_sources=["ipcc.ch", "noaa.gov"],
        topic="Climate & Environment", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q014",
        question="How does deforestation contribute to climate change?",
        expected_keywords=["carbon sink", "emissions", "Amazon", "biodiversity", "CO2"],
        topic="Climate & Environment", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q015",
        question="What are nature-based solutions for climate mitigation?",
        expected_keywords=["reforestation", "wetlands", "mangroves", "soil carbon", "biodiversity"],
        topic="Climate & Environment", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q016",
        question="How is ocean acidification affecting marine ecosystems?",
        expected_keywords=["pH", "coral", "calcification", "CO2", "shellfish"],
        expected_sources=["nature.com", "noaa.gov"],
        topic="Climate & Environment", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q017",
        question="What are the projected sea level rise scenarios by 2100?",
        expected_keywords=["meters", "ice sheet", "Greenland", "thermal expansion", "IPCC"],
        expected_sources=["ipcc.ch"],
        topic="Climate & Environment", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q018",
        question="How effective are electric vehicles in reducing lifecycle carbon emissions?",
        expected_keywords=["lifecycle", "battery", "grid", "manufacturing", "emissions"],
        topic="Climate & Environment", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q019",
        question="What is the role of methane in short-term climate forcing?",
        expected_keywords=["GWP", "short-lived", "livestock", "wetlands", "100-year"],
        expected_sources=["ipcc.ch"],
        topic="Climate & Environment", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q020",
        question="How are climate tipping points defined and what are the main ones?",
        expected_keywords=["threshold", "irreversible", "AMOC", "ice sheet", "permafrost"],
        expected_sources=["nature.com"],
        topic="Climate & Environment", difficulty="hard",
    ),

    # -----------------------------------------------------------------------
    # Domain 3 — Healthcare & Medicine (q021–q030)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q021",
        question="How does mRNA vaccine technology work?",
        expected_keywords=["mRNA", "spike protein", "immune response", "lipid nanoparticle", "antibody"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov", "who.int"],
        topic="Healthcare & Medicine", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q022",
        question="What is the current state of Alzheimer's disease treatments?",
        expected_keywords=["amyloid", "tau", "lecanemab", "clinical trial", "FDA"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov", "fda.gov"],
        topic="Healthcare & Medicine", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q023",
        question="How does CRISPR-Cas9 gene editing work?",
        expected_keywords=["guide RNA", "DNA", "cut", "repair", "off-target"],
        expected_sources=["nature.com", "science.org"],
        topic="Healthcare & Medicine", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q024",
        question="What are the leading causes of antimicrobial resistance?",
        expected_keywords=["antibiotic", "resistance", "overuse", "bacteria", "mutation"],
        expected_sources=["who.int"],
        topic="Healthcare & Medicine", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q025",
        question="How are CAR-T cell therapies being used in cancer treatment?",
        expected_keywords=["chimeric", "T-cell", "lymphoma", "leukemia", "immunotherapy"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov"],
        topic="Healthcare & Medicine", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q026",
        question="What are the main risk factors for cardiovascular disease?",
        expected_keywords=["hypertension", "cholesterol", "smoking", "diabetes", "obesity"],
        topic="Healthcare & Medicine", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q027",
        question="How do GLP-1 receptor agonists work for weight loss?",
        expected_keywords=["semaglutide", "Ozempic", "appetite", "insulin", "Wegovy"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov", "fda.gov"],
        topic="Healthcare & Medicine", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q028",
        question="What is the gut microbiome and its role in human health?",
        expected_keywords=["bacteria", "diversity", "immunity", "inflammation", "dysbiosis"],
        expected_sources=["nature.com", "pubmed.ncbi.nlm.nih.gov"],
        topic="Healthcare & Medicine", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q029",
        question="How is AI being applied to drug discovery pipelines?",
        expected_keywords=["protein folding", "AlphaFold", "molecular", "screening", "clinical"],
        expected_sources=["nature.com", "deepmind.com"],
        topic="Healthcare & Medicine", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q030",
        question="What are the global burden and drivers of mental health disorders?",
        expected_keywords=["depression", "anxiety", "WHO", "disability", "treatment gap"],
        expected_sources=["who.int"],
        topic="Healthcare & Medicine", difficulty="easy",
    ),

    # -----------------------------------------------------------------------
    # Domain 4 — Economics & Finance (q031–q040)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q031",
        question="How do central banks use quantitative easing to stimulate the economy?",
        expected_keywords=["bond", "money supply", "interest rate", "Fed", "liquidity"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q032",
        question="What are the main causes of the 2008 global financial crisis?",
        expected_keywords=["subprime", "CDO", "Lehman", "mortgage", "derivatives"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q033",
        question="How does inflation targeting work as a monetary policy framework?",
        expected_keywords=["2%", "central bank", "CPI", "expectations", "Taylor rule"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q034",
        question="What is modern monetary theory (MMT) and its main criticisms?",
        expected_keywords=["sovereign", "deficit", "currency", "inflation", "fiscal"],
        topic="Economics & Finance", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q035",
        question="How do cryptocurrency markets differ from traditional financial markets?",
        expected_keywords=["decentralized", "volatility", "blockchain", "regulation", "liquidity"],
        topic="Economics & Finance", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q036",
        question="What drives income inequality and what policies can address it?",
        expected_keywords=["Gini", "wealth", "tax", "education", "redistribution"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q037",
        question="What is the impact of AI automation on labor markets?",
        expected_keywords=["jobs", "displacement", "productivity", "skills", "reskilling"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q038",
        question="How do supply chain disruptions affect global trade?",
        expected_keywords=["logistics", "inventory", "reshoring", "just-in-time", "geopolitics"],
        topic="Economics & Finance", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q039",
        question="What is deglobalization and what trends are driving it?",
        expected_keywords=["tariffs", "reshoring", "geopolitics", "supply chain", "protectionism"],
        topic="Economics & Finance", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q040",
        question="How does sovereign debt affect a country's economic stability?",
        expected_keywords=["debt-to-GDP", "default", "IMF", "bond yields", "fiscal"],
        topic="Economics & Finance", difficulty="hard",
    ),

    # -----------------------------------------------------------------------
    # Domain 5 — Energy & Clean Tech (q041–q050)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q041",
        question="What are the leading battery technologies for grid-scale energy storage?",
        expected_keywords=["lithium", "flow battery", "sodium", "grid", "MWh"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q042",
        question="How does offshore wind energy compare to onshore wind?",
        expected_keywords=["capacity factor", "installation", "cost", "turbine", "offshore"],
        topic="Energy & Clean Tech", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q043",
        question="What is green hydrogen and how is it produced?",
        expected_keywords=["electrolysis", "renewable", "fuel cell", "H2", "electrolyzer"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q044",
        question="What is the current levelized cost of energy (LCOE) for solar PV?",
        expected_keywords=["LCOE", "$/MWh", "solar", "utility scale", "cost"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q045",
        question="How does nuclear fusion differ from nuclear fission, and what is the state of fusion research?",
        expected_keywords=["plasma", "tokamak", "ITER", "net energy", "confinement"],
        topic="Energy & Clean Tech", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q046",
        question="How are smart grids enabling better energy management?",
        expected_keywords=["demand response", "IoT", "distribution", "real-time", "flexibility"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q047",
        question="What are the main barriers to global decarbonization?",
        expected_keywords=["fossil fuels", "investment", "policy", "technology", "developing countries"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q048",
        question="How does concentrated solar power (CSP) differ from photovoltaic solar?",
        expected_keywords=["thermal", "mirrors", "heat storage", "PV", "molten salt"],
        topic="Energy & Clean Tech", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q049",
        question="What role does geothermal energy play in the clean energy transition?",
        expected_keywords=["heat", "Iceland", "baseload", "drilling", "steam"],
        topic="Energy & Clean Tech", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q050",
        question="How are small modular reactors (SMRs) expected to change nuclear energy?",
        expected_keywords=["modular", "factory", "GW", "safety", "cost"],
        topic="Energy & Clean Tech", difficulty="hard",
    ),

    # -----------------------------------------------------------------------
    # Domain 6 — Geopolitics & Policy (q051–q060)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q051",
        question="What are the main drivers of US-China geopolitical competition?",
        expected_keywords=["trade", "Taiwan", "semiconductor", "military", "influence"],
        topic="Geopolitics & Policy", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q052",
        question="How has the Russia-Ukraine conflict reshaped European security?",
        expected_keywords=["NATO", "defense spending", "energy", "sanctions", "sovereignty"],
        topic="Geopolitics & Policy", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q053",
        question="What is the role of the United Nations in managing global conflicts?",
        expected_keywords=["Security Council", "veto", "peacekeeping", "resolution", "mandate"],
        topic="Geopolitics & Policy", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q054",
        question="How are AI regulations evolving across the EU, US, and China?",
        expected_keywords=["EU AI Act", "NIST", "regulation", "risk-based", "governance"],
        topic="Geopolitics & Policy", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q055",
        question="What is the Belt and Road Initiative and its global impact?",
        expected_keywords=["China", "infrastructure", "debt", "developing", "trade"],
        topic="Geopolitics & Policy", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q056",
        question="How is BRICS changing the global economic order?",
        expected_keywords=["Brazil", "Russia", "India", "China", "dollar", "reserve"],
        topic="Geopolitics & Policy", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q057",
        question="What are the key provisions of the Paris Agreement on climate change?",
        expected_keywords=["NDC", "1.5", "2 degrees", "UNFCCC", "net zero"],
        expected_sources=["unfccc.int"],
        topic="Geopolitics & Policy", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q058",
        question="How do semiconductor export controls affect global tech competition?",
        expected_keywords=["CHIPS Act", "export control", "TSMC", "EDA", "advanced node"],
        topic="Geopolitics & Policy", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q059",
        question="What is the current state of global nuclear arms control?",
        expected_keywords=["NPT", "START", "deterrence", "proliferation", "disarmament"],
        topic="Geopolitics & Policy", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q060",
        question="How does disinformation spread and what policies can counter it?",
        expected_keywords=["social media", "deepfake", "propaganda", "platform", "media literacy"],
        topic="Geopolitics & Policy", difficulty="medium",
    ),

    # -----------------------------------------------------------------------
    # Domain 7 — Space & Science (q061–q070)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q061",
        question="What is NASA's Artemis program and its goals?",
        expected_keywords=["Moon", "SLS", "Gateway", "astronaut", "2026"],
        expected_sources=["nasa.gov"],
        topic="Space & Science", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q062",
        question="How does SpaceX Starship change the economics of space launch?",
        expected_keywords=["reusable", "payload", "cost per kg", "Raptor", "Starship"],
        topic="Space & Science", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q063",
        question="What have we learned from the James Webb Space Telescope?",
        expected_keywords=["infrared", "galaxy", "exoplanet", "early universe", "JWST"],
        expected_sources=["nasa.gov", "nature.com"],
        topic="Space & Science", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q064",
        question="What is dark matter and what is the evidence for its existence?",
        expected_keywords=["gravitational", "galaxy rotation", "lensing", "WIMP", "CMB"],
        expected_sources=["nature.com", "arxiv.org"],
        topic="Space & Science", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q065",
        question="How do exoplanet atmospheres get studied?",
        expected_keywords=["transmission spectroscopy", "JWST", "biosignature", "atmosphere", "transit"],
        expected_sources=["nasa.gov"],
        topic="Space & Science", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q066",
        question="What is the current plan for humans on Mars?",
        expected_keywords=["SpaceX", "radiation", "journey", "habitat", "timeline"],
        topic="Space & Science", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q067",
        question="How does GPS technology work?",
        expected_keywords=["satellite", "triangulation", "atomic clock", "signal", "orbit"],
        topic="Space & Science", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q068",
        question="What are gravitational waves and how are they detected?",
        expected_keywords=["LIGO", "spacetime", "merger", "strain", "interferometer"],
        expected_sources=["ligo.org"],
        topic="Space & Science", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q069",
        question="What is the Fermi paradox and the main proposed solutions?",
        expected_keywords=["extraterrestrial", "silence", "filter", "Drake equation", "civilization"],
        topic="Space & Science", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q070",
        question="How do planetary defense missions protect Earth from asteroid impacts?",
        expected_keywords=["DART", "deflection", "Near Earth Object", "kinetic impactor", "tracking"],
        expected_sources=["nasa.gov"],
        topic="Space & Science", difficulty="medium",
    ),

    # -----------------------------------------------------------------------
    # Domain 8 — Business & Markets (q071–q080)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q071",
        question="What is the current global semiconductor market size and growth forecast?",
        expected_keywords=["billion", "CAGR", "TSMC", "AI chips", "2025"],
        topic="Business & Markets", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q072",
        question="How has generative AI changed the SaaS industry?",
        expected_keywords=["AI native", "copilot", "productivity", "pricing", "disruption"],
        topic="Business & Markets", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q073",
        question="What are the key growth drivers for the electric vehicle market?",
        expected_keywords=["battery cost", "charging", "policy", "range", "adoption"],
        topic="Business & Markets", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q074",
        question="How is the global pharmaceutical market structured?",
        expected_keywords=["branded", "generic", "biologics", "R&D", "regulation"],
        topic="Business & Markets", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q075",
        question="What are the main business models for AI companies?",
        expected_keywords=["API", "SaaS", "fine-tuning", "inference", "enterprise"],
        topic="Business & Markets", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q076",
        question="How has the e-commerce landscape evolved post-pandemic?",
        expected_keywords=["Amazon", "logistics", "returns", "social commerce", "omnichannel"],
        topic="Business & Markets", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q077",
        question="What is the impact of rising interest rates on startup valuations?",
        expected_keywords=["venture capital", "discount rate", "burn rate", "valuation", "funding"],
        topic="Business & Markets", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q078",
        question="How is the insurance industry being disrupted by AI and InsurTech?",
        expected_keywords=["underwriting", "risk", "claims", "telematics", "personalization"],
        topic="Business & Markets", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q079",
        question="What are the main competitive dynamics in the cloud computing market?",
        expected_keywords=["AWS", "Azure", "GCP", "multi-cloud", "market share"],
        topic="Business & Markets", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q080",
        question="How is the global logistics industry adapting to automation?",
        expected_keywords=["warehouse", "robotics", "autonomous", "last mile", "supply chain"],
        topic="Business & Markets", difficulty="medium",
    ),

    # -----------------------------------------------------------------------
    # Domain 9 — Education & Society (q081–q090)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q081",
        question="How is generative AI changing higher education?",
        expected_keywords=["plagiarism", "tutoring", "curriculum", "assessment", "ChatGPT"],
        topic="Education & Society", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q082",
        question="What does the research say about the effectiveness of online learning?",
        expected_keywords=["completion rate", "MOOC", "engagement", "outcomes", "hybrid"],
        topic="Education & Society", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q083",
        question="What are the social impacts of social media on adolescent mental health?",
        expected_keywords=["depression", "anxiety", "comparison", "Instagram", "screen time"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov"],
        topic="Education & Society", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q084",
        question="How does universal basic income (UBI) affect work and poverty?",
        expected_keywords=["pilot", "Finland", "poverty", "employment", "transfer"],
        topic="Education & Society", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q085",
        question="What are the causes and consequences of global urbanization?",
        expected_keywords=["megacity", "infrastructure", "migration", "slum", "growth"],
        topic="Education & Society", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q086",
        question="How is the global fertility rate changing and what are the implications?",
        expected_keywords=["birth rate", "aging", "workforce", "population", "decline"],
        topic="Education & Society", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q087",
        question="What is the digital divide and how can it be addressed?",
        expected_keywords=["access", "internet", "rural", "developing", "broadband"],
        topic="Education & Society", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q088",
        question="How does immigration affect host country economies?",
        expected_keywords=["labor", "fiscal", "integration", "skills", "remittances"],
        topic="Education & Society", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q089",
        question="What are the long-term educational outcomes of early childhood interventions?",
        expected_keywords=["kindergarten", "cognitive", "earnings", "Perry", "Head Start"],
        expected_sources=["pubmed.ncbi.nlm.nih.gov"],
        topic="Education & Society", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q090",
        question="How is aging population demographics changing healthcare systems?",
        expected_keywords=["elderly", "pension", "long-term care", "workforce", "chronic disease"],
        topic="Education & Society", difficulty="medium",
    ),

    # -----------------------------------------------------------------------
    # Domain 10 — Cybersecurity (q091–q100)
    # -----------------------------------------------------------------------
    BenchmarkQuestion(
        question_id="q091",
        question="What are the most common attack vectors in enterprise cybersecurity?",
        expected_keywords=["phishing", "ransomware", "supply chain", "zero-day", "social engineering"],
        topic="Cybersecurity", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q092",
        question="How does zero-trust security architecture work?",
        expected_keywords=["never trust", "verify", "micro-segmentation", "identity", "least privilege"],
        topic="Cybersecurity", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q093",
        question="What are the cybersecurity implications of quantum computing?",
        expected_keywords=["encryption", "RSA", "post-quantum", "Shor", "NIST"],
        expected_sources=["nist.gov"],
        topic="Cybersecurity", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q094",
        question="How do state-sponsored cyberattacks differ from criminal ones?",
        expected_keywords=["APT", "nation-state", "espionage", "critical infrastructure", "attribution"],
        topic="Cybersecurity", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q095",
        question="What is the current ransomware threat landscape?",
        expected_keywords=["double extortion", "RaaS", "cryptocurrency", "healthcare", "critical"],
        topic="Cybersecurity", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q096",
        question="How is AI being used both offensively and defensively in cybersecurity?",
        expected_keywords=["adversarial", "detection", "generative", "threat intelligence", "automation"],
        topic="Cybersecurity", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q097",
        question="What are the main provisions of GDPR and its global influence?",
        expected_keywords=["data protection", "consent", "right to erasure", "fine", "controller"],
        topic="Cybersecurity", difficulty="easy",
    ),
    BenchmarkQuestion(
        question_id="q098",
        question="How does supply chain security risk manifest in software development?",
        expected_keywords=["SolarWinds", "dependency", "SBOM", "open source", "CI/CD"],
        topic="Cybersecurity", difficulty="hard",
    ),
    BenchmarkQuestion(
        question_id="q099",
        question="What is the role of threat intelligence in proactive defense?",
        expected_keywords=["IOC", "TTPs", "MITRE ATT&CK", "sharing", "hunting"],
        topic="Cybersecurity", difficulty="medium",
    ),
    BenchmarkQuestion(
        question_id="q100",
        question="How do bug bounty programs improve software security?",
        expected_keywords=["HackerOne", "vulnerability", "disclosure", "reward", "patch"],
        topic="Cybersecurity", difficulty="easy",
    ),
]


def load_benchmark(framework=None):
    """
    Load all 100 questions into the given framework (or the module singleton).

    Usage::

        from app.evaluation.benchmark_questions import load_benchmark
        from app.evaluation.framework import evaluation_framework

        load_benchmark(evaluation_framework)
    """
    from app.evaluation.framework import evaluation_framework as _default_fw
    target = framework or _default_fw
    target.add_questions(BENCHMARK_QUESTIONS)
    return target
