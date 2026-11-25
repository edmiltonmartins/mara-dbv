# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Catálogo estruturado da Biblioteca do Chat DBV (Conteúdos Pré-Feitos por Categoria).

Permite que desbravadores, conselheiros e instrutores consultem guias rápidos já estruturados,
explorem os manuais oficiais por categoria e iniciem conversas ou simulados com 1 clique.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemBiblioteca:
    id: str
    titulo: str
    subtitulo: str
    categoria: str
    logo_relativo: str
    badge: str
    resumo_markdown: str
    pergunta_consulta: str
    tema_simulado: str


CATALOGO_BIBLIOTECA: list[ItemBiblioteca] = [
    # ==================== UNIFORMES (RUD) ====================
    ItemBiblioteca(
        id="rud_bolsos_insignias",
        titulo="Mapa de Bolsos, Emblemas e Tiras (Uniforme de Gala)",
        subtitulo="Medidas exatas em milímetros para camisa/blusa cáqui conforme o RUD/DSA.",
        categoria="UNIFORMES",
        logo_relativo="D1/Imagem 005.jpg",
        badge="Uniforme de Gala",
        resumo_markdown="""
| Item / Insígnia | Localização Oficial (RUD/DSA) | Medida / Referência |
| :--- | :--- | :--- |
| **Tira com o Nome do Clube (D4)** | Manga direita (abaixo da costura do ombro) | **15 mm (1,5 cm)** abaixo da costura |
| **Emblema D1 (Triângulo Oficial)** | Manga direita, abaixo da tira do clube | **50 mm (5,0 cm)** abaixo da costura do ombro |
| **Distintivo de Função / Tira de Cargo** | Manga direita, logo acima do Emblema D1 | Centralizado entre a tira e o D1 |
| **Emblema do Campo (Associação/Missão)** | Manga esquerda | **15 mm (1,5 cm)** abaixo da costura do ombro |
| **Globinho de Líder (L1)** | Manga esquerda, abaixo do emblema do campo | Centralizado abaixo do emblema do campo |
| **Divisa de Classes** | Manga esquerda, abaixo do emblema do campo/L1 | Em ordem decrescente (Guia no topo) |
| **Tira de Nome (Identificação)** | Acima da tampa do bolso direito | Centralizada, rente à costura superior |
| **Distintivos de Classes (Pins)** | Tampa do bolso esquerdo | Da direita para a esquerda de quem veste (Amigo → Guia) |
| **Insígnia de Excelência** | Acima da tampa do bolso esquerdo | Centralizada acima dos distintivos |
""",
        pergunta_consulta="Explique detalhadamente a posição de todos os emblemas, tiras e distintivos nos bolsos e mangas do Uniforme de Gala segundo o RUD da DSA.",
        tema_simulado="Gere um simulado sobre medidas e posições dos emblemas D1, D2, D3, D4, L1, bolsos e mangas no Regulamento de Uniformes (RUD).",
    ),
    ItemBiblioteca(
        id="rud_emblemas_d1_a_l4",
        titulo="Significado e Uso dos Emblemas (D1 a D4 e L1 a L4)",
        subtitulo="Onde aplicar cada emblema oficial de Desbravador e de Liderança.",
        categoria="UNIFORMES",
        logo_relativo="L1/globo-lider-desbravador.jpg",
        badge="Emblemas Oficiais",
        resumo_markdown="""
- **Emblema D1:** Triângulo equilátero com fundo vermelho, escudo branco, espada azul e inscrição *DESBRAVADORES*. Usado na manga direita da camisa/blusa do uniforme de gala e no boné.
- **Emblema D2:** Triângulo com globo ao fundo (sem o nome escrito). Usado no **prendedor de lenço (argola)** e na **fivela do cinto**.
- **Emblema D3:** Triângulo simplificado com fundo vermelho e linhas em amarelo/preto. Usado no **lenço oficial amarelo** e no uniforme de atividades.
- **Emblema D4:** Tira curva em tecido com borda vermelha e inscrição *CLUBE DE DESBRAVADORES* + nome do clube.
- **Emblema L1 (Líder):** Octógono com globo e D3 centralizado — exclusivo para Líderes investidos.
- **Emblemas L2, L3 e L4:** Insígnias de **Líder Master** (1 estrela) e **Líder Master Avançado** (2 estrelas).
""",
        pergunta_consulta="Qual é a diferença de aplicação entre os emblemas D1, D2, D3, D4 e os emblemas de liderança L1, L2, L3 e L4 segundo o RUD?",
        tema_simulado="Gere um simulado sobre os emblemas D1, D2, D3, D4 e L1 a L4 e suas aplicações no uniforme.",
    ),
    ItemBiblioteca(
        id="rud_faixa_especialidades",
        titulo="Faixa de Especialidades: Regras e Ordem dos Itens",
        subtitulo="Uso correto da faixa sobre o ombro direito e o que pode ser afixado.",
        categoria="UNIFORMES",
        logo_relativo="D2/JPG/D2.jpg",
        badge="Faixa Oficial",
        resumo_markdown="""
- **Quem pode usar:** Apenas desbravadores ou líderes que possuam ao menos **1 especialidade investida**.
- **Como vestir:** Posta sobre o **ombro direito**, transversalmente, apoiada sob o passador (platina) direito e fechada na altura do quadril esquerdo.
- **Bandeira Nacional:** Bordada na parte frontal superior da faixa, na altura do peito.
- **O que pode conter:** Insígnias de especialidades e mestrados conquistados, pins de eventos oficiais autorizados (Camporis DSA/União/Campo) na parte inferior/traseira conforme normas do RUD.
""",
        pergunta_consulta="Quais são todas as regras do RUD para o uso da faixa de especialidades, posição da bandeira nacional e organização das insígnias?",
        tema_simulado="Gere um simulado sobre as regras da faixa de especialidades no Regulamento de Uniformes (RUD).",
    ),

    # ==================== CLASSES REGULARES E AVANÇADAS ====================
    ItemBiblioteca(
        id="classes_amigo_companheiro",
        titulo="Classes de Amigo (10 anos) e Companheiro (11 anos)",
        subtitulo="Cores, requisitos gerais, leitura bíblica e classes avançadas (Amigo da Natureza / Companheiro de Excursionismo).",
        categoria="CLASSES",
        logo_relativo="Classes/b1_amigo.png",
        badge="10 e 11 Anos",
        resumo_markdown="""
### 🔵 Classe de Amigo (Azul — 10 anos)
- **Requisitos centrais:** Memorizar e explicar o **Voto e a Lei do Desbravador**, ler o livro do Clube do Livro Juvenil, conhecer a composição da Bandeira Nacional e aprender os nós básicos.
- **Classe Avançada:** *Amigo da Natureza*.

### 🔴 Classe de Companheiro (Vermelho — 11 anos)
- **Requisitos centrais:** Memorizar os livros do **Antigo Testamento**, estudar os efeitos nocivos do fumo/álcool, caminhada de excursionismo e fogueiras.
- **Classe Avançada:** *Companheiro de Excursionismo*.
""",
        pergunta_consulta="Quais são os principais requisitos das classes de Amigo (10 anos) e Companheiro (11 anos) e de suas respectivas classes avançadas?",
        tema_simulado="Gere um simulado sobre os requisitos das Classes de Amigo e Companheiro.",
    ),
    ItemBiblioteca(
        id="classes_pesquisador_pioneiro",
        titulo="Classes de Pesquisador (12 anos) e Pioneiro (13 anos)",
        subtitulo="Orientação por bússola e estrelas, Novo Testamento, acampamento e resgate básico.",
        categoria="CLASSES",
        logo_relativo="Classes/b3_pesquisador.png",
        badge="12 e 13 Anos",
        resumo_markdown="""
### 🟢 Classe de Pesquisador (Verde — 12 anos)
- **Requisitos centrais:** Memorizar os livros do **Novo Testamento**, orientação sem bússola (Cruzeiro do Sul e Órion), estudo da criação e rastreamento de animais.
- **Classe Avançada:** *Pesquisador de Campo e Bosque*.

### ⚫ Classe de Pioneiro (Cinza/Preto — 13 anos)
- **Requisitos centrais:** Estudo das Bem-Aventuranças, construção de móveis de acampamento com amarras, fogo sem fósforo e primeiros socorros em trilhas.
- **Classe Avançada:** *Pioneiro de Novas Fronteiras*.
""",
        pergunta_consulta="Quais são os requisitos das classes de Pesquisador (12 anos) e Pioneiro (13 anos), incluindo orientação e pioneiria?",
        tema_simulado="Gere um simulado sobre as Classes de Pesquisador e Pioneiro.",
    ),
    ItemBiblioteca(
        id="classes_excursionista_guia",
        titulo="Classes de Excursionista (14 anos) e Guia (15 anos)",
        subtitulo="Doutrina do Santuário, mordomia, liderança de unidade e preparação para Líder.",
        categoria="CLASSES",
        logo_relativo="Classes/b6_guia.png",
        badge="14 e 15 Anos",
        resumo_markdown="""
### 🟣 Classe de Excursionista (Vinho/Roxo — 14 anos)
- **Requisitos centrais:** Obra do Espírito Santo, eventos finais, caminhada longa com mochila e orientação topográfica.
- **Classe Avançada:** *Excursionista na Mata*.

### 🟡 Classe de Guia (Amarelo — 15 anos)
- **Requisitos centrais:** Estudo do **Santuário**, mordomia cristã, dons espirituais, ensino de especialidades para classes menores e liderança prática.
- **Classe Avançada:** *Guia de Exploração*.
""",
        pergunta_consulta="Quais são os principais requisitos das classes de Excursionista (14 anos) e Guia (15 anos) nos manuais da DSA?",
        tema_simulado="Gere um simulado completo sobre as Classes de Excursionista e Guia.",
    ),

    # ==================== MANUAL ADMINISTRATIVO & HISTÓRIA/IDEAIS ====================
    ItemBiblioteca(
        id="adm_sistema_unidades",
        titulo="Sistema de Unidades, Conselheiro e Capitão",
        subtitulo="Estrutura de 6 a 8 desbravadores, separação por sexo e atribuições no clube.",
        categoria="ADMINISTRATIVO",
        logo_relativo="D3/JPG/D3_a.jpg",
        badge="Gestão do Clube",
        resumo_markdown="""
- **Tamanho da Unidade:** Composta por **6 a 8 desbravadores**, sempre separados por sexo (unidades masculinas e unidades femininas) e agrupados por faixa etária.
- **Conselheiro(a):** Membro da diretoria (18+ anos) que acompanha a unidade em todas as atividades, reuniões, cantinho da unidade e acampamentos.
- **Capitão(ã) e Secretário(a):** Escolhidos entre os próprios desbravadores da unidade (com mandato de 3 a 6 meses para estimular o rodízio de liderança).
- **Cantinho da Unidade:** Momento coração da reunião semanal (chamada, pontualidade, uniforme, devocional e planejamento).
""",
        pergunta_consulta="Como funciona o Sistema de Unidades no Clube de Desbravadores, qual o número ideal de membros e os papéis do Conselheiro, Capitão e Secretário?",
        tema_simulado="Gere um simulado sobre o Sistema de Unidades e cargos da Diretoria conforme o Manual Administrativo.",
    ),
    ItemBiblioteca(
        id="adm_ideais_oficiais",
        titulo="Ideais dos Desbravadores: Voto, Lei, Alvo, Lema e Objetivo",
        subtitulo="Texto integral oficial da DSA e explicação pedagógica de cada ideal.",
        categoria="HISTORIA_IDEAIS",
        logo_relativo="D1/JPG/D1.jpg",
        badge="Ideais DSA",
        resumo_markdown="""
- **Voto:** *"Pela graça de Deus, serei puro, bondoso e leal; guardarei a Lei do Desbravador, serei servo de Deus e amigo de todos."*
- **Lei do Desbravador:**
  1. Observar a devoção matinal;
  2. Cumprir fielmente a parte que me corresponde;
  3. Cuidar do meu corpo;
  4. Manter a consciência limpa;
  5. Ser cortês e obediente;
  6. Andar com reverência na casa de Deus;
  7. Ter sempre um cântico no coração;
  8. Ir aonde Deus mandar.
- **Alvo:** *"A mensagem do advento a todo o mundo em minha geração."*
- **Lema:** *"O amor de Cristo me motiva."*
- **Objetivo:** *"Salvar do pecado e guiar no serviço."*
""",
        pergunta_consulta="Explique o significado de cada item do Voto e da Lei do Desbravador, além do Alvo, Lema e Objetivo segundo os manuais da DSA.",
        tema_simulado="Gere um simulado sobre o Voto, a Lei, o Alvo, o Lema, o Objetivo e o Hino dos Desbravadores.",
    ),

    # ==================== ESPECIALIDADES ====================
    ItemBiblioteca(
        id="esp_nos_amarras_acampamento",
        titulo="Especialidades Fundamentais: Nós e Amarras & Arte de Acampar",
        subtitulo="Nós básicos exigidos nas classes, amarras de pioneiria e regras de acampamento.",
        categoria="ESPECIALIDADES",
        logo_relativo="Classes/master_guilde_logo.png",
        badge="Artes Práticas",
        resumo_markdown="""
- **Nós essenciais:** Simples, Direito, Cirurgião, Lais de Guia, Cego, Escota, Pescador, Volta do Fiel (Calafate) e Volta da Ribeira.
- **Amarras de Pioneiria:**
  - **Amarra Quadrada:** Une duas varas em ângulo reto (90°).
  - **Amarra Diagonal:** Une duas varas que se cruzam em ângulo agudo/obtuso (inicia com Volta da Ribeira).
  - **Amarra Paralela (Redonda):** Une duas varas paralelamente para alongar mastros.
  - **Amarra Contínua:** Usada para tampos de mesa, pontes e estrados.
""",
        pergunta_consulta="Quais são os principais nós e amarras exigidos no Clube de Desbravadores e para que serve cada um nos manuais da DSA?",
        tema_simulado="Gere um simulado sobre a utilidade de cada nó e amarra na especialidade de Nós e Amarras.",
    ),

    # ==================== ORDEM UNIDA & CIVISMO ====================
    ItemBiblioteca(
        id="ou_comandos_formacoes",
        titulo="Ordem Unida e Civismo: Vozes de Comando e Bandeiras",
        subtitulo="Voz de advertência, comando propriamente dito, voz de execução e posição em civismo.",
        categoria="ADMINISTRATIVO",
        logo_relativo="D4/JPG/D4_a.jpg",
        badge="Ordem Unida",
        resumo_markdown="""
- **As 3 Etapas da Voz de Comando:**
  1. **Voz de Advertência:** Alerta a tropa/unidade (ex: *"Atenção, Clube!"* ou *"Unidade!"*).
  2. **Comando Propriamente Dito:** Indica o movimento que será feito (ex: *"Direita..."*, *"Ordinário..."*).
  3. **Voz de Execução:** Determina o instante exato da ação, curta e enérgica (ex: *"Volver!"*, *"Marche!"*).
- **Posição de Civismo no Hasteamento:** Desbravadores uniformizados permanecem em posição de **Sentido (Firme)**, sem fazer saudação Maranata durante a execução do Hino Nacional ou hasteamento.
""",
        pergunta_consulta="Explique as etapas das vozes de comando na Ordem Unida e as regras de civismo e hasteamento de bandeiras nos manuais da DSA.",
        tema_simulado="Gere um simulado sobre Ordem Unida, vozes de comando e protocolo de bandeiras.",
    ),

    # ==================== OMDs VIGENTES, GEMAS BÍBLICAS, LIDERANÇA & CAMPORI ====================
    ItemBiblioteca(
        id="omds_vigentes_atualizacoes",
        titulo="OMDs Vigentes (001 a 021/2024) e Orientações 2026",
        subtitulo="Resumo rápido das retificações oficiais da DSA: idades, casamento, desfile no sábado, livros e SGC.",
        categoria="ADMINISTRATIVO",
        logo_relativo="D1/JPG/D1.jpg",
        badge="Normas Vigentes",
        resumo_markdown="""
| Norma Oficial DSA | Regra Vigente no Clube |
| :--- | :--- |
| **OMD 004 (Desfile no Sábado)** | É vedada participação em desfiles cívicos/militares no sábado; exceções estritas seguem orientação pastoral/missional sem banda marcial competitiva. |
| **OMD 009 (Uniforme em Casamento)** | Regulamenta o uso do Uniforme de Gala pelos noivos investidos e pela Guarda de Honra / Teto de Aço. |
| **OMD 011 (Corte de Idades)** | Define a regra oficial de idade por ano civil/aniversário para ingresso aos 10 anos e classes regulares. |
| **OMD 019/2023 (Coordenador SGC)** | Regulamenta a função de Coordenador do Sistema de Gerenciamento de Clubes na Associação/Missão. |
| **OMD 020/2024 (Nomes de Clubes)** | Estabelece critérios bíblicos, naturais e históricos permitidos e nomes vedados para batizar clubes. |
| **OMD 021/2024 (Livros das Classes)** | Atualiza oficialmente os livros de leitura das classes regulares e de liderança. |
| **Orientações 2026 & Espaço da Calma** | Protocolo MAP/MDA de inclusão sensorial, acolhimento neurodivergente e uso de cordões oficiais. |
""",
        pergunta_consulta="Quais são as principais determinações das OMDs vigentes da DSA (como OMD 004, OMD 009, OMD 011, OMD 020/2024, OMD 021/2024) e das Orientações 2026?",
        tema_simulado="Regras atualizadas pelas OMDs da DSA (idades, uniforme em casamento, desfile no sábado, livros das classes e nomes de clubes)",
    ),
    ItemBiblioteca(
        id="classes_gemas_versiculos_biblicos",
        titulo="Textos e Gemas Bíblicas das 6 Classes (Amigo a Guia)",
        subtitulo="Referência rápida de bolso dos capítulos e versículos exigidos em Descoberta Espiritual.",
        categoria="CLASSES",
        logo_relativo="Classes/b6_guia.png",
        badge="Descoberta Espiritual",
        resumo_markdown="""
- **Amigo (10 anos):** Criação, 10 Pragas, 12 Tribos, 39 livros do Antigo Testamento; versos como *Salmo 23*, *Êxodo 20:3-17*, *João 3:16*, *Filipenses 4:13*.
- **Companheiro (11 anos):** 27 livros do Novo Testamento; *Mateus 5:3-12 (Bem-Aventuranças)*, *Isaías 41:9-10*, *Provérbios 22:6*, *Salmo 8*.
- **Pesquisador (12 anos):** *Eclesiastes 12:1*, *João 3:1-21*, *Isaías 1:18*, *Salmo 51:10*, *Salmo 19*.
- **Pioneiro (13 anos):** *1 Pedro 1:24-25*, *1 Reis 18:21*, *Mateus 24:37-39*, *Romanos 12:1-2*, *Apocalipse 1:3*.
- **Excursionista (14 anos):** *Romanos 8:28*, *Apocalipse 21:1-3*, *2 Pedro 1:20-21*, *1 João 2:14*, *2 Crônicas 20:20*, *Salmo 46*.
- **Guia (15 anos):** *1 Coríntios 13*, *2 Crônicas 7:14*, *Apocalipse 22:18-20*, *2 Timóteo 4:6-7*, *Romanos 8:38-39*, *Mateus 6:33-34* + 3 Mensagens Angélicas (*Ap 14:6-12*), 7 Igrejas e 12 Fundamentos da Nova Jerusalém.
""",
        pergunta_consulta="Liste os textos bíblicos, capítulos e gemas de memorização exigidos na seção Descoberta Espiritual dos cartões de Amigo até Guia.",
        tema_simulado="Textos bíblicos, doutrinas e seção Descoberta Espiritual das Classes Regulares (Amigo a Guia)",
    ),
    ItemBiblioteca(
        id="lideranca_lider_lm_lma",
        titulo="Trilha de Liderança: Líder, Líder Master e LMA",
        subtitulo="Requisitos progressivos para maiores de 16/18 anos, validade de cartões (OMD 006) e Mestrados.",
        categoria="CLASSES",
        logo_relativo="L1/globo-lider-desbravador.jpg",
        badge="Liderança DSA",
        resumo_markdown="""
- **Líder de Desbravadores:** Início aos 16 anos (investidura aos 18+), membro batizado, concluir as 6 classes regulares (ou Cartão Agrupado), Curso de Treinamento de Diretoria (CTD 10h+), Ano Bíblico Jovem e atuação ativa na diretoria.
- **Líder Master (LM):** Pré-requisito de ser Líder investido, conclusão de Mestrados de especialidades, direção/instrução prática e leitura de livros do Espírito de Profecia.
- **Líder Master Avançado (LMA):** Pré-requisito de Líder Master, capacitação de líderes regionais, pesquisa/produção técnica e avaliação conforme Recomendações Oficiais LMA da DSA.
- **Validade (OMD 006 e OMD 014):** Atenção aos prazos regulamentares de conclusão e assinatura da coordenação regional/campo.
""",
        pergunta_consulta="Quais são os requisitos oficiais e regras das OMDs para as classes de Líder, Líder Master (LM) e Líder Master Avançado (LMA)?",
        tema_simulado="Requisitos dos cartões de Líder, Líder Master, Líder Master Avançado e regras das OMDs 002, 006, 013 e 014",
    ),
    ItemBiblioteca(
        id="campori_dsa_2027_guia",
        titulo="VI Campori Sul-Americano DSA 2027 — Orientações e Boletins",
        subtitulo="Regras gerais de inscrição, requisitos prévios do clube, pontuação e boletins oficiais 2026.",
        categoria="CAMPORI",
        logo_relativo="D2/JPG/D2.jpg",
        badge="Campori DSA 2027",
        resumo_markdown="""
- **Documentos Oficiais Indexados:** *Manual de Orientações VI Campori DSA 2027*, *Manual de Eventos* e *Boletins Oficiais Nº 01/2026 e Nº 02/2026*.
- **Preparação do Clube:** Cadastro e seguro anual em dia no SGC, cumprimento dos pré-requisitos comunitários, espirituais e administrativos nos prazos de cada etapa, padronização do uniforme e estrutura de cozinha/área de acampamento.
- **Acessibilidade:** Estrutura oficial de acolhimento (*Espaço da Calma MAP/MDA*) para desbravadores com necessidades sensoriais.
""",
        pergunta_consulta="Quais são as principais orientações, datas, eventos e regras dos Boletins Oficiais 2026 para o VI Campori Sul-Americano da DSA 2027?",
        tema_simulado="Manual de Orientações e Boletins Oficiais do VI Campori Sul-Americano da DSA 2027",
    ),
]
