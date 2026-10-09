import { useState, type ReactNode } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import brandLogo from './logo_120.png'
import './App.css'

const applicationUrl = 'https://api.basarat.live/docs'
const contactEmail = 'ahmedkhanofficials@gmail.com'

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link aria-label="Basarat home" className={`brand${compact ? ' brand-compact' : ''}`} to="/">
      <img alt="" className="brand-mark" src={brandLogo} />
      <span>basarat<span className="brand-period">.</span></span>
    </Link>
  )
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="site-header">
      <div className="header-inner">
        <Brand />
        <button
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          className="menu-toggle"
          onClick={() => setMenuOpen(!menuOpen)}
          type="button"
        >
          <span />
          <span />
        </button>
        <nav aria-label="Main navigation" className={menuOpen ? 'main-nav nav-open' : 'main-nav'}>
          <NavLink onClick={() => setMenuOpen(false)} to="/">Overview</NavLink>
          <NavLink onClick={() => setMenuOpen(false)} to="/privacy">Privacy</NavLink>
          <NavLink onClick={() => setMenuOpen(false)} to="/terms">Terms</NavLink>
          <a className="nav-cta" href={applicationUrl} rel="noreferrer" target="_blank">
            Open the app <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </div>
    </header>
  )
}

function ArrowIcon() {
  return <span aria-hidden="true" className="arrow-icon">↗</span>
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <Brand compact />
          <p>Thoughtful market intelligence for the Pakistan Stock Exchange.</p>
        </div>
        <nav aria-label="Footer navigation" className="footer-nav">
          <Link to="/">Home</Link>
          <Link to="/privacy">Privacy policy</Link>
          <Link to="/terms">Terms of service</Link>
          <a href={`mailto:${contactEmail}`}>Contact</a>
        </nav>
        <div className="footer-bottom">
          <span>© 2026 Basarat. All rights reserved.</span>
          <span>Market insight, made clearer.</span>
        </div>
      </div>
    </footer>
  )
}

const features = [
  {
    number: '01',
    icon: '↗',
    title: 'Market intelligence',
    description: 'Explore PSX market activity, company data, and the signals shaping the day.',
  },
  {
    number: '02',
    icon: '⌁',
    title: 'Research & forecasts',
    description: 'Bring quantitative models and market context together to support your research.',
  },
  {
    number: '03',
    icon: '◌',
    title: 'Portfolio perspective',
    description: 'Understand portfolio exposure, risk measures, and Shariah screening insights.',
  },
]

function HomePage() {
  return (
    <main>
      <section className="hero-section">
        <div className="hero-grid" aria-hidden="true" />
        <div className="page-container hero-content">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-dot" /> INVEST WITH MORE CONTEXT</div>
            <h1>Clarity for a market that <span>never stands still.</span></h1>
            <p className="hero-description">
              Basarat is an AI-powered investment intelligence platform built around the
              Pakistan Stock Exchange—bringing market data, quantitative research, and
              portfolio insight into one place.
            </p>
            <div className="hero-actions">
              <a className="button button-primary" href={applicationUrl} rel="noreferrer" target="_blank">
                Explore Basarat <ArrowIcon />
              </a>
              <Link className="button button-secondary" to="/privacy">How we handle your data</Link>
            </div>
            <p className="hero-caption">Independent research tools. Your decisions remain your own.</p>
          </div>
          <div className="hero-visual" aria-label="Illustration of market insights" role="img">
            <div className="visual-topline"><span>MARKET PULSE</span><span className="live-indicator">● LIVE DATA</span></div>
            <div className="visual-market">
              <div>
                <span className="market-label">KSE 100 INDEX</span>
                <span className="market-value">Market insight<span className="market-period">.</span></span>
              </div>
              <span className="market-chip">PSX · PAKISTAN</span>
            </div>
            <div className="chart-wrap">
              <div className="chart-labels" aria-hidden="true"><span>RESEARCH</span><span>CONTEXT</span><span>RISK</span></div>
              <svg aria-hidden="true" className="market-chart" fill="none" viewBox="0 0 510 190">
                <defs>
                  <linearGradient id="chart-fill" x1="255" x2="255" y1="12" y2="190" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#4dd8c4" stopOpacity=".23" />
                    <stop offset="1" stopColor="#4dd8c4" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d="M0 153C31 153 37 132 65 138s30 25 54 8 27-44 57-34 35 16 58-10 37-18 55-2 30 6 52-28 35-14 55-2 41-16 58-43 36 0 56-20 29-3 49-7v190H0V153Z" fill="url(#chart-fill)" />
                <path d="M0 153C31 153 37 132 65 138s30 25 54 8 27-44 57-34 35 16 58-10 37-18 55-2 30 6 52-28 35-14 55-2 41-16 58-43 36 0 56-20 29-3 49-7" stroke="#4dd8c4" strokeLinecap="round" strokeWidth="3" />
                <circle cx="509" cy="0" r="6" fill="#4dd8c4" stroke="#0b1f2a" strokeWidth="4" />
              </svg>
              <div className="chart-axis" aria-hidden="true"><span>DATA</span><span>ANALYSIS</span><span>DECISIONS</span></div>
            </div>
            <div className="visual-footer"><span>One clearer view of the market.</span><span className="visual-sparkle">✳</span></div>
          </div>
        </div>
        <div className="hero-bottom page-container">
          <span>BUILT FOR THE PAKISTAN STOCK EXCHANGE</span>
          <span>DATA · ANALYSIS · PERSPECTIVE</span>
        </div>
      </section>

      <section aria-labelledby="features-title" className="features-section page-container">
        <div className="section-heading">
          <div>
            <div className="eyebrow eyebrow-dark">A MORE INFORMED VIEW</div>
            <h2 id="features-title">The market, in context.</h2>
          </div>
          <p>Purpose-built tools to help investors explore the data, understand the signals, and ask better questions.</p>
        </div>
        <div className="feature-grid">
          {features.map((feature) => (
            <article className="feature-card" key={feature.number}>
              <div className="feature-card-top"><span>{feature.number}</span><span aria-hidden="true" className="feature-icon">{feature.icon}</span></div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="closing-section">
        <div className="page-container closing-inner">
          <div>
            <div className="eyebrow">START WITH THE BIG PICTURE</div>
            <h2>Make room for a little more clarity.</h2>
            <p>Explore the Basarat platform and its investment research capabilities.</p>
          </div>
          <a className="button button-light" href={applicationUrl} rel="noreferrer" target="_blank">
            Open the Basarat app <ArrowIcon />
          </a>
        </div>
      </section>
      <p className="disclaimer page-container">
        Basarat provides informational and analytical tools only. Nothing on this site is investment,
        financial, legal, or tax advice, nor a recommendation to buy or sell any security.
      </p>
    </main>
  )
}

function PolicyLayout({ children, title, description }: { children: ReactNode; title: string; description: string }) {
  return (
    <main className="legal-page">
      <section className="legal-hero">
        <div className="page-container">
          <div className="eyebrow"><span className="eyebrow-dot" /> BASARAT · TRUST & TRANSPARENCY</div>
          <h1>{title}</h1>
          <p>{description}</p>
          <span className="updated-date">Last updated: October 10, 2026</span>
        </div>
      </section>
      <div className="page-container legal-content">
        <aside className="legal-aside">
          <div className="aside-label">ON THIS PAGE</div>
          <a href="#overview">Overview</a>
          <a href="#information">Information</a>
          <a href="#use-and-protection">Use & protection</a>
          <a href="#your-choices">Your choices</a>
          <a href="#contact">Contact</a>
        </aside>
        <article className="legal-article">{children}</article>
      </div>
    </main>
  )
}

function PrivacyPage() {
  return (
    <PolicyLayout
      description="A clear explanation of the information used to sign in to Basarat with Google, and how we handle it."
      title="Privacy policy"
    >
      <section id="overview">
        <span className="article-index">01 / OVERVIEW</span>
        <h2>Your privacy matters.</h2>
        <p>
          This policy describes how Basarat handles information when you choose to sign in or
          create an account using Google. Basarat is an investment intelligence platform focused
          on the Pakistan Stock Exchange (PSX).
        </p>
        <p>
          Google sign-in is optional. You can use another sign-in method where one is available.
          This website is informational and is not the Basarat product interface.
        </p>
      </section>

      <section id="information">
        <span className="article-index">02 / INFORMATION</span>
        <h2>What we receive from Google</h2>
        <p>
          When you authorize Google sign-in, Google provides basic account and profile information
          needed to identify your account. Depending on what is available from your Google profile,
          this includes:
        </p>
        <ul>
          <li><strong>Email address</strong> — to create or match your Basarat account and identify you when you sign in.</li>
          <li><strong>Name</strong> — to display your profile name in Basarat.</li>
          <li><strong>Profile picture</strong> — to display your account avatar when available.</li>
          <li><strong>Google account identifier</strong> — a unique identifier used to recognize your Google-linked account.</li>
        </ul>
        <p>
          Basarat does not receive your Google password. Google sign-in credentials are validated
          to complete authentication; Basarat does not use them to access your Google account or
          other Google services.
        </p>
      </section>

      <section id="use-and-protection">
        <span className="article-index">03 / USE & PROTECTION</span>
        <h2>How we use and safeguard information</h2>
        <p>We use the information above only to:</p>
        <ul>
          <li>create your account or match it to an existing Basarat account;</li>
          <li>authenticate you and maintain your signed-in session; and</li>
          <li>show your name and profile image in your Basarat account.</li>
        </ul>
        <p>
          Account information is stored by Basarat for these purposes and is handled using
          access-controlled application systems. We use reasonable administrative and technical
          safeguards to protect it against unauthorized access, loss, or misuse. Information is
          shared only as needed to operate and secure the service, comply with applicable law, or
          protect users and Basarat; it is not sold.
        </p>
        <p>
          We retain account information while your account remains active and for a limited period
          where needed to meet legal, security, or service obligations. Deletion from active
          systems may not immediately remove data held in protected backups or records we are
          required to keep.
        </p>
      </section>

      <section id="your-choices">
        <span className="article-index">04 / YOUR CHOICES</span>
        <h2>Your choices and Google’s role</h2>
        <p>
          You can choose whether to use Google sign-in. You can review or revoke Basarat’s Google
          account access through your Google Account’s third-party connections settings. Revoking
          access does not itself delete an existing Basarat account.
        </p>
        <p>
          To ask us to access, correct, or delete your Basarat account information, contact us
          using the details below. We may need to verify your request before taking action.
        </p>
        <p>
          Google handles its own services and personal information under
          {' '}<a href="https://policies.google.com/privacy" rel="noreferrer" target="_blank">Google’s Privacy Policy</a>.
          This policy applies to Basarat’s handling of information we receive for sign-in; it does
          not replace Google’s policy.
        </p>
      </section>

      <section id="contact">
        <span className="article-index">05 / CONTACT</span>
        <h2>Questions about privacy?</h2>
        <p>
          Contact the Basarat team at <a href={`mailto:${contactEmail}`}>{contactEmail}</a> for
          privacy questions or account-data requests.
        </p>
      </section>
    </PolicyLayout>
  )
}

function TermsPage() {
  return (
    <PolicyLayout
      description="The terms that apply when you visit the Basarat information site or use its investment research tools."
      title="Terms of service"
    >
      <section id="overview">
        <span className="article-index">01 / OVERVIEW</span>
        <h2>Using Basarat</h2>
        <p>
          These Terms of Service apply to your access to and use of Basarat, an investment
          intelligence platform focused on the Pakistan Stock Exchange. By accessing or using
          Basarat, you agree to these terms. If you do not agree, do not use the service.
        </p>
        <p>
          Basarat is an independent product and is not affiliated with, endorsed by, or operated
          by Google. Google sign-in is provided for account authentication.
        </p>
      </section>

      <section id="information">
        <span className="article-index">02 / INFORMATION</span>
        <h2>Research, data & no investment advice</h2>
        <p>
          Basarat may provide market data, analysis, forecasts, screening, portfolio tools, or
          other informational content. This material is provided for general information and
          educational purposes only. It is not investment, financial, legal, or tax advice, and
          does not constitute a recommendation, offer, or solicitation to buy or sell any
          security or financial product.
        </p>
        <p>
          Market data and analytical outputs may be delayed, incomplete, estimated, or incorrect.
          Forecasts and model outputs are inherently uncertain and are not guarantees of future
          results. You are responsible for independently evaluating information and for your
          investment decisions. Consult a qualified professional where appropriate.
        </p>
      </section>

      <section id="use-and-protection">
        <span className="article-index">03 / RESPONSIBLE USE</span>
        <h2>Your account and acceptable use</h2>
        <p>
          Provide accurate account information and take reasonable steps to protect your sign-in
          credentials. You are responsible for activity carried out through your account. Notify
          us if you believe your account has been accessed without authorization.
        </p>
        <p>You agree not to:</p>
        <ul>
          <li>use the service unlawfully or to violate another person’s rights;</li>
          <li>attempt to disrupt, damage, probe, or gain unauthorized access to the service or its systems;</li>
          <li>misuse, resell, or redistribute service data in breach of applicable law or third-party rights; or</li>
          <li>misrepresent Basarat’s analysis as guaranteed, personalized financial advice.</li>
        </ul>
      </section>

      <section id="your-choices">
        <span className="article-index">04 / AVAILABILITY & LIABILITY</span>
        <h2>Service availability and limitations</h2>
        <p>
          We may update, suspend, or discontinue features to maintain or improve the service.
          To the extent permitted by law, Basarat is provided “as is” and “as available,”
          without guarantees that it will be uninterrupted, error-free, or suitable for a
          particular purpose.
        </p>
        <p>
          To the extent permitted by applicable law, Basarat is not liable for indirect or
          consequential losses, investment losses, or decisions made in reliance on information
          provided by the service. Nothing in these terms limits liability where it cannot
          lawfully be limited.
        </p>
        <p>
          We may revise these terms as the service changes. The updated date above indicates the
          latest revision. Continued use after an update means you accept the revised terms.
        </p>
      </section>

      <section id="contact">
        <span className="article-index">05 / CONTACT</span>
        <h2>Get in touch</h2>
        <p>
          Questions about these terms? Contact <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.
        </p>
      </section>
    </PolicyLayout>
  )
}

function NotFoundPage() {
  return (
    <main className="not-found page-container">
      <div className="eyebrow eyebrow-dark">404 · PAGE NOT FOUND</div>
      <h1>Let’s get you back on track.</h1>
      <p>The page you’re looking for may have moved or no longer exists.</p>
      <Link className="button button-primary" to="/">Return home <ArrowIcon /></Link>
    </main>
  )
}

function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route element={<HomePage />} path="/" />
        <Route element={<PrivacyPage />} path="/privacy" />
        <Route element={<TermsPage />} path="/terms" />
        <Route element={<NotFoundPage />} path="*" />
      </Routes>
      <Footer />
    </>
  )
}

export default App
