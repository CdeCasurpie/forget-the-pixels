% Document Class LaTeX para la Tesis de UTEC.
% Arquitectura refactorizada: Geometría absoluta nativa (PGF/TikZ) + geometry.

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{tesisutec}

%% ============================================================================
%  Configuracion de la clase
%% ============================================================================

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{book}}
\ProcessOptions\relax
\LoadClass[11pt,a4paper]{book}

\def\@makechapterhead#1{%
  {\parindent \z@ \centering
    \normalfont
    \ifnum \c@secnumdepth >\m@ne
      \if@mainmatter
        \Large\bfseries \@chapapp\space \thechapter
        \par\nobreak
      \fi
    \fi
    \interlinepenalty\@M
    \Large \bfseries #1\par\nobreak
    \vskip 40\p@
    \thispagestyle{empty}
  }}

\renewcommand{\@chapapp}{\MakeUppercase{CAP\'ITULO}}

%% ============================================================================
%  Paquetes y comandos para el documento
%% ============================================================================

\RequirePackage[utf8]{inputenc}
\PassOptionsToPackage{english}{babel}
\PassOptionsToPackage{spanish,es-tabla,es-nodecimaldot}{babel}
\RequirePackage{babel}
\RequirePackage{xcolor}

\RequirePackage{lmodern}
\RequirePackage{anyfontsize}

\RequirePackage{tikz} 
\usetikzlibrary{calc, positioning}

% Colores del rediseño arquitectónico
\definecolor{charcoal}{RGB}{5, 6, 6}    
\definecolor{gold}{RGB}{0, 185, 247}     
\definecolor{darkgold}{RGB}{0, 185, 247}   
\definecolor{offwhite}{RGB}{255, 255, 255} 
\definecolor{utecblue}{RGB}{0, 185, 247}  

\RequirePackage{titlesec}
\RequirePackage[subfigure]{tocloft}

\newcommand{\orcid}[1]{\href{https://orcid.org/#1}{\includegraphics[width=10pt]{./images/ORCID128px.png}}}

\newcommand\customchapter[1]{%
  \chapter*{\center \Large \vspace{-4.5cm} #1 }%
  \addcontentsline{toc}{section}{\bfseries #1 }%
  \markboth{#1}{#1}%
}

\newcommand{\introsection}[1]{%
  \section*{\hspace{2em}#1}%
  \addcontentsline{toc}{section}{\bfseries #1 }%
}

\addtocounter{secnumdepth}{1}
\setcounter{tocdepth}{6}
\newcounter{dummy}

\newcommand\addtotoc[1]{%
  \refstepcounter{dummy}%
  \addcontentsline{toc}{chapter}{#1}%
}

\addto\captionsspanish{%
    \renewcommand{\contentsname}{\hfill\bfseries \Large{TABLA DE CONTENIDO} }%
}

\cftsetindents{section}{0em}{2em}
\cftsetindents{subsection}{1em}{2.5em}

\renewcommand\cftaftertoctitle{\hfill\mbox{}}
\addtocontents{toc}{\hfill{P\'ag.}\par}

\renewcommand{\thechapter}{\Roman{chapter}}
\renewcommand{\thesection}{\arabic{chapter}.\arabic{section}}

\newcommand\bhrule{\typeout{------------------------------------------------------------------------------}}

% ====================================================================
% Configuraciones Listas
% ====================================================================

\renewcommand\listoffigures{%
  \begin{spacing}{1}%
    \setlength{\parskip}{1pt}%
    \if@twocolumn
      \@restonecoltrue\onecolumn
    \else
      \@restonecolfalse
    \fi
    \chapter*{\vspace{-2.0cm}\begin{center}\Large{\textbf{\'INDICE DE FIGURAS}}\end{center}%
      \@mkboth{\MakeUppercase\listfigurename}{\MakeUppercase\listfigurename}}%
    \@starttoc{lof}%
    \if@restonecol\twocolumn\fi
    \cleardoublepage
  \end{spacing}%
}

\addto\captionsspanish{\renewcommand{\listfigurename}{\hfill\bfseries\Large{\'INDICE DE FIGURAS}\hfill }}
\renewcommand{\thefigure}{\arabic{chapter}.\arabic{figure}}
\renewcommand{\cftfigfont}{Figura }

\renewcommand\listoftables{%
  \begin{spacing}{1}%
    \setlength{\parskip}{1pt}%
    \if@twocolumn
      \@restonecoltrue\onecolumn
    \else
      \@restonecolfalse
    \fi
    \chapter*{\vspace{-2.0cm}\begin{center}\Large{\textbf{\'INDICE DE TABLAS}}\end{center}%
      \@mkboth{\MakeUppercase\listtablename}{\MakeUppercase\listtablename}}%
    \@starttoc{lot}%
    \if@restonecol\twocolumn\fi
    \cleardoublepage
  \end{spacing}%
}

\addto\captionsspanish{\renewcommand{\listtablename}{\hfill\bfseries \Large{\'INDICE DE TABLAS}\hfill }}
\renewcommand{\thetable}{\arabic{chapter}.\arabic{table}}
\renewcommand{\cfttabfont}{Tabla }

%% ============================================================================
%  Configuracion del documento
%% ============================================================================

\newcommand\btypeout[1]{\bhrule\typeout{\space #1}\bhrule}
\RequirePackage{setspace}
\onehalfspacing
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{2.0ex \@plus 0.5ex \@minus 0.2ex}

% -----------------------------------------------------------------------------
% Mapeo de márgenes lógicos alineados con topología física del PDF
\RequirePackage[
  a4paper,
  left=3.0cm,
  top=3.0cm,
  right=3.0cm,
  bottom=3.0cm,
  headheight=20pt,
  headsep=0.25in,
  footskip=0.3in
]{geometry}
% -----------------------------------------------------------------------------

\raggedbottom
\setlength{\topskip}{1\topskip \@plus 5\p@}
\doublehyphendemerits=10000
\brokenpenalty=10000
\widowpenalty=9999
\clubpenalty=9999
\interfootnotelinepenalty=9999
\RequirePackage{fancyhdr}
\chead{}\rfoot{\thepage}\lfoot{}\cfoot{}
\renewcommand{\headrulewidth}{0pt}
\fancyhead{}
\pagestyle{fancy}
\renewcommand{\chaptermark}[1]{\btypeout{\thechapter\space #1}\markboth{\@chapapp\ \thechapter\ #1}{\@chapapp\ \thechapter\ #1}}
\renewcommand{\sectionmark}[1]{}
\renewcommand{\subsectionmark}[1]{}
\def\cleardoublepage{\clearpage\if@twoside \ifodd\c@page\else
\hbox{}
\thispagestyle{empty}
\newpage
\if@twocolumn\hbox{}\newpage\fi\fi\fi}
\RequirePackage{amsmath,amsfonts,amssymb,amscd,amsthm,xspace}
\theoremstyle{plain}
\newtheorem{example}{Example}[chapter]
\newtheorem{theorem}{Theorem}[chapter]
\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\RequirePackage[centerlast,small,sc]{caption}
\setlength{\captionmargin}{20pt}
\newcommand{\fref}[1]{Figure~\ref{#1}}
\newcommand{\tref}[1]{Table~\ref{#1}}
\newcommand{\eref}[1]{Equation~\ref{#1}}
\newcommand{\cref}[1]{Chapter~\ref{#1}}
\newcommand{\sref}[1]{Section~\ref{#1}}
\newcommand{\aref}[1]{Appendix~\ref{#1}}
\renewcommand{\topfraction}{0.85}
\renewcommand{\bottomfraction}{.85}
\renewcommand{\textfraction}{0.1}
\renewcommand{\dbltopfraction}{.85}
\renewcommand{\floatpagefraction}{0.75}
\renewcommand{\dblfloatpagefraction}{.75}
\setcounter{topnumber}{9}
\setcounter{bottomnumber}{9}
\setcounter{totalnumber}{20}
\setcounter{dbltopnumber}{9}
\RequirePackage{graphicx}
\RequirePackage{epstopdf}
\RequirePackage[scriptsize]{subfigure}
\RequirePackage{booktabs}
\RequirePackage{rotating}
\RequirePackage{listings}

\RequirePackage[pdfpagemode={UseOutlines},bookmarks=true,bookmarksopen=true,
   bookmarksopenlevel=0,bookmarksnumbered=true,hypertexnames=false,
   colorlinks,linkcolor={black},citecolor={blue},urlcolor={red},
   pdfstartview={FitV},unicode,breaklinks=true]{hyperref}
\pdfstringdefDisableCommands{
   \let\\\space
   \def\includegraphics#1{}
   \def\orcid#1{}
}

\newcommand*{\supervisor}[1]{\def\supname{#1}}
\newcommand*{\examiner}[1]{\def\examname{#1}}
\newcommand*{\examinertwo}[1]{\def\examnametwo{#1}}
\newcommand*{\president}[1]{\def\presname{#1}}
\newcommand*{\major}[1]{\def\majorname{#1}}
\newcommand*{\degree}[1]{\def\degreename{#1}}
\renewcommand*{\author}[1]{\def\authornames{#1}}
\newcommand*{\authorid}[1]{\def\studentid{#1}}
\newcommand*{\department}[1]{\def\deptname{#1}}
\newcommand*{\subject}[1]{\def\subjectname{#1}}
\newcommand*{\keywords}[1]{\def\keywordnames{#1}}
\renewcommand*{\date}[1]{\def\dateMY{#1}}
\supervisor  {}
\examiner    {}
\major       {}
\degree      {}
\author      {}
\subject     {}
\keywords    {}

\titleformat{\section}
  {\normalfont \bfseries}{\thesection}{1em}{}
\titleformat{\subsection}
  {\normalfont \bfseries}{\thesubsection}{1em}{}
\setlength{\cftchapnumwidth}{3em}

% Parser algebraico estructurado
\def\tesis@parse@title@i#1:#2\@nil{%
    {\fontsize{42pt}{48pt}\selectfont\bfseries\color{gold}#1}\par
    \vskip 0.6cm
    {\LARGE\color{offwhite}\ignorespaces #2\par}%
}
\def\tesis@parse@title{%
    \expandafter\in@\expandafter:\expandafter{\@title}%
    \ifin@
        \expandafter\tesis@parse@title@i\@title\@nil
    \else
        {\fontsize{42pt}{48pt}\selectfont\bfseries\color{gold}\@title\par}%
    \fi
}

%% ====================================================================
%% Portada (Anclaje vectorial referenciado al límite de página)
%% ============================================================================
\renewcommand\maketitle{%
  \btypeout{Title Page}%
  \hypersetup{pdftitle={\@title}, pdfsubject=\subjectname, pdfauthor=\authornames, pdfkeywords=\keywordnames}%
  \begin{titlepage}
  \thispagestyle{empty}

  \begin{tikzpicture}[remember picture, overlay]
      % 1. LAYER BASE (Fondo sólido A4 estricto)
      \fill[charcoal] (current page.south west) rectangle (current page.north east);

      % 2. MÁSCARA SEMÁNTICA (Mapa centrado)
    \node[anchor=south west, opacity=0.5] at (current page.south west) {%
        \includegraphics[height=\paperheight, keepaspectratio]{images/lima.png}%
    };

      % 4. NODO IDENTITARIO (Logo escalado)
      \node[anchor=south west, inner sep=0] at ($(current page.south west) + (1.2cm, 1.2cm)$) {%
          \includegraphics[width=5cm]{images/logo-utec-white.png}%
      };

      % 5. BLOQUES TIPOGRÁFICOS ANCLADOS ABSOLUTAMENTE
      \node[anchor=north east, align=right] at ($(current page.north east) + (-2.5cm, -3cm)$) {%
          {\color{gold}\textbf{\Large UNIVERSIDAD DE INGENIER\'IA}} \\ 
          {\color{gold}\textbf{\Large Y TECNOLOG\'IA}} \\[0.2cm]
          {\color{offwhite}\small CARRERA DE \MakeUppercase{\deptname}}%
      };

      \node[anchor=east, align=right, text width=14cm] at ($(current page.east) + (-2.5cm, 1.5cm)$) {%
          \raggedleft
          \tesis@parse@title
          \vskip 1.5cm
          {\color{gold}\small\textbf{TRABAJO DE INVESTIGACI\'ON}}\par\vskip 0.2cm
          {\color{offwhite}\small Para optar el grado de \degreename\ en}\par\vskip 0.1cm
          {\color{offwhite}\small \majorname}\par
      };

      \node[anchor=south east, align=right, text=offwhite] at ($(current page.south east) + (-2.5cm, 4.5cm)$) {%
          {\color{gold}\small\textbf{AUTOR(ES):}} \\[0.15cm]
          \normalsize \authornames \\[0.8cm]
          {\color{gold}\small\textbf{ASESOR(ES):}} \\[0.15cm]
          \normalsize \supname
      };

      \node[anchor=south east, align=right] at ($(current page.south east) + (-2.5cm, 2.5cm)$) {%
          {\color{offwhite}Lima - Per\'u} \\
          {\color{gold}\textbf{\dateMY}}%
      };

  \end{tikzpicture}
  \mbox{}
  \end{titlepage}
  \setcounter{footnote}{0}%
  \global\let\thanks\relax
  \global\let\maketitle\relax
  \global\let\@thanks\@empty
  \global\let\@author\@empty
  \global\let\title\relax
  \global\let\author\relax
  \global\let\and\relax
  \cleardoublepage
}

% ====================================================================
% Firmas, Dedicatoria y Agradecimientos
%% ============================================================================

\newcommand\Aprobado[1]{%
  \setstretch{1.5}%  
  \thispagestyle{empty}%
  \noindent La tesis\\
  \textbf{\@title} \\
  ha sido aprobada.
  {\normalsize #1}%

  \vspace{2.5cm}%
  \hfill\rule[0.5em]{16.5em}{0.5pt} \\  
  ${~}$\hfill \presname \\

  \vspace{1.5cm}%
  \hfill\rule[0.5em]{16.5em}{0.5pt} \\  
  ${~}$\hfill \supname \\
  
  \vspace{1.5cm}%
  \hfill\rule[0.5em]{16.5em}{0.5pt} \\  
  ${~}$\hfill \examname \\

  \vspace{1.5cm}%
  \hfill\rule[0.5em]{16.5em}{0.5pt} \\  
  ${~}$\hfill \examnametwo \\
  \clearpage
}

\newcommand\dedicatory[1]{%
  \setstretch{1.0}%  
  \thispagestyle{empty}%
  \null\vfil
  \vskip 60pt
  \vspace{4.5cm}%
  ${~}$\hfill \textit{Dedicatoria}: \\
  \begin{flushright}{ \sl #1}\end{flushright}%
  \vfil\null
  \cleardoublepage
  \setstretch{1.5}% 
}

\newcommand\acknowledgements[1]{%
  \setstretch{1.0}% 
  \thispagestyle{empty}%
  \null\vfil
  \vskip 60pt
  \vspace{4.5cm}%
  ${~}$\hfill \textit{Agradecimientos}: \\
  \begin{flushright}{ \sl #1}\end{flushright}%
  \vfil\null
  \cleardoublepage
  \setstretch{1.5}% 
}

\newcommand\resumen[1]{%
  \btypeout{Resumen}%
  \addtotoc{Resumen}%
  \thispagestyle{plain}%
  \null\vfil
  \begin{center}{\huge\bfseries Resumen\par}\end{center}%
  {\normalsize #1}%
  \vfil\vfil\null
}

\newcommand\abstract[1]{%
  \btypeout{Abstract}%
  \addtotoc{Abstract}%
  \thispagestyle{plain}%
  \null\vfil
  \begin{center}{\huge\bfseries Abstract\par}\end{center}%
  {\normalsize #1}%
  \vfil\vfil\null
}

\newcommand\recommendations[1]{%
  \btypeout{RECOMENDACIONES}%
  \addtotoc{RECOMENDACIONES}%
  \clearpage
  \thispagestyle{plain}%
  \begin{center}{\Large \textbf{RECOMENDACIONES} \par}\end{center}%
  \vspace{0.5cm}%
  {\normalsize #1}%
  \vfil\vfil\null
  \clearpage
}

\endinput
%% End of file `tesisutec.cls'.