import { useEffect, useState, type ReactNode } from 'react'
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
    title: 'PSX market intelligence',
    description: 'Explore Pakistan Stock Exchange market activity, company fundamentals, financial news, and market sentiment.',
  },
  {
    number: '02',
    icon: '⌁',
    title: 'Research & forecasts',
    description: 'Review technical indicators, quantitative research, and 5-, 10-, and 20-day model forecasts. Forecasts are estimates, not guarantees.',
  },
  {
    number: '03',
    icon: '◌',
    title: 'Portfolio & risk tools',
    description: 'Track watchlists and portfolio transactions you enter, explore risk measures, configure alerts, and review Shariah screening insights.',
  },
  {
    number: '04',
    icon: '✳',
    title: 'Investor community & AI',
    description: 'Discuss market ideas with the community and use the in-app assistant to explore investment research in context.',
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

      <section aria-labelledby="google-data-title" className="data-transparency">
        <div className="page-container data-transparency-inner">
          <div className="data-icon" aria-hidden="true">◎</div>
          <div className="data-transparency-copy">
            <div className="eyebrow eyebrow-dark">A CLEARER SIGN-IN</div>
            <h2 id="google-data-title">Google sign-in. Only the basics.</h2>
            <p>
              If you choose Google sign-in in the Basarat app, we use your email address,
              Google account identifier, and—when available—your name and profile photo to
              create or identify your Basarat account and show your profile. We do not receive
              your Google password or access Gmail, Drive, or Contacts.
            </p>
          </div>
          <Link className="data-policy-link" to="/privacy">
            Read our privacy policy <ArrowIcon />
          </Link>
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
            Explore the live API <ArrowIcon />
          </a>
        </div>
      </section>
      <p className="disclaimer page-container">
        Basarat’s market data, analysis, model forecasts, and portfolio tools are for informational
        purposes only. Nothing on this site is investment,
        financial, legal, or tax advice, nor a recommendation to buy or sell any security.
      </p>
    </main>
  )
}

function PolicyLayout({ children, title, description }: { children: ReactNode; title: string; description: string }) {
  useEffect(() => {
    document.title = `${title} | Basarat`
    const descriptionTag = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    descriptionTag?.setAttribute('content', description)
  }, [description, title])

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
          {title === 'Privacy policy' ? (
            <>
              <a href="#google-data">Google data</a>
              <a href="#other-data">Other information</a>
              <a href="#use-and-protection">Use & sharing</a>
              <a href="#retention-and-choices">Retention & choices</a>
              <a href="#contact">Contact</a>
            </>
          ) : (
            <>
              <a href="#information">Information</a>
              <a href="#use-and-protection">Use & protection</a>
              <a href="#your-choices">Your choices</a>
              <a href="#contact">Contact</a>
            </>
          )}
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
          This Privacy Policy explains what information Basarat collects, how we use and share it,
          and the choices available to you. It applies to the Basarat mobile application, the
          Basarat investment intelligence service for the Pakistan Stock Exchange (PSX), and this
          public website.
        </p>
        <p>
          Google sign-in is optional. If you choose it, the Google account information described
          below is used to create or access your Basarat account. We do not receive your Google
          password and do not use Google sign-in to access Google services such as Gmail, Drive,
          or Contacts.
        </p>
      </section>

      <section id="google-data">
        <span className="article-index">02 / GOOGLE SIGN-IN DATA</span>
        <h2>Information received from Google</h2>
        <p>
          When you choose “Continue with Google,” Basarat receives the following basic profile
          information from Google, to the extent it is available and authorized by you:
        </p>
        <ul>
          <li><strong>Email address</strong> — used to identify you, create your account, or connect Google sign-in to an existing Basarat account with the same email address.</li>
          <li><strong>Name</strong> — used as your account’s display name when provided.</li>
          <li><strong>Profile picture URL</strong> — used as your Basarat account avatar when provided.</li>
          <li><strong>Google account identifier</strong> — a unique account identifier used to recognize your Google-linked account on later sign-ins.</li>
        </ul>
        <p>
          Basarat processes the Google sign-in token to authenticate your request. The token is
          used for authentication and is not stored as part of your Basarat profile. Basarat does
          not receive your Google password, request access to your Google content, or use this
          information for advertising, sale of data, or training generative AI models.
        </p>
      </section>

      <section id="other-data">
        <span className="article-index">03 / OTHER INFORMATION</span>
        <h2>Information you provide when using Basarat</h2>
        <p>
          If you use the Basarat application and its features, we also collect information you
          choose to provide or create in the service. Depending on which features you use, this
          may include:
        </p>
        <ul>
          <li><strong>Account and profile details</strong>, such as your username, name, optional phone number, profile image, and account preferences.</li>
          <li><strong>Investment information</strong>, such as watchlists, portfolio transactions you enter, investment horizon, risk tolerance, sector preferences, and alert settings.</li>
          <li><strong>Content and communications</strong>, such as community posts and comments, messages or prompts you send to the in-app assistant, and saved assistant conversations.</li>
          <li><strong>App and device information</strong>, such as device name, platform, and a push-notification registration token when you register a device for notifications.</li>
        </ul>
        <p>
          You can choose whether to provide optional profile details and whether to use features
          that require additional information. If you provide portfolio or investment details,
          they are used to operate the corresponding portfolio, analytics, alert, or
          personalization features.
        </p>
      </section>

      <section id="use-and-protection">
        <span className="article-index">04 / USE & SHARING</span>
        <h2>How we use information</h2>
        <p>We use information to:</p>
        <ul>
          <li>create, secure, and maintain your account and authenticate sign-ins;</li>
          <li>display and update your profile information;</li>
          <li>provide the market research, portfolio analysis, alerts, community, and assistant features you choose to use;</li>
          <li>maintain, troubleshoot, and protect the reliability and security of Basarat; and</li>
          <li>respond to your support requests and comply with legal obligations.</li>
        </ul>
        <p>
          <strong>Google user data is used only to provide or improve user-facing features that
          are visible in the Basarat application.</strong> In particular, Google profile data is
          used for account registration, account matching, sign-in, and your Basarat profile. It
          is not sold, used for advertising, or used to train generalized AI or machine-learning
          models.
        </p>
        <p>
          We do not sell personal information. We share information only when necessary with
          service providers that host, store, secure, or help operate Basarat; when you ask us to
          use a feature that requires another provider; when required by law or valid legal
          process; or when reasonably necessary to protect users, the service, or legal rights.
          Service providers are permitted to process information only to provide their services
          to Basarat.
        </p>
        <p>
          If you use the in-app AI assistant, the prompts and context you submit may be sent to
          the AI service provider to generate a response. Do not include information in a prompt
          that you do not want processed for that purpose. Google sign-in data is not used as
          training data for that provider.
        </p>
      </section>

      <section id="retention-and-choices">
        <span className="article-index">05 / STORAGE & YOUR CHOICES</span>
        <h2>Storage, security, and retention</h2>
        <p>
          Basarat stores account and feature data in systems used to operate the service. Google
          account identifiers and the profile information associated with your Basarat account
          are retained while the account remains active, so that we can recognize and provide
          access to your account. We apply administrative and technical safeguards intended to
          protect personal information from unauthorized access, alteration, disclosure, or loss.
          No method of storage or transmission can be guaranteed to be completely secure.
        </p>
        <p>
          You may stop using Google sign-in at any time and revoke Basarat’s access in your Google
          Account’s third-party connections settings. Revoking access does not automatically
          delete information already associated with your Basarat account.
        </p>
        <p>
          To request access to, correction of, or deletion of your Basarat account information,
          email us using the contact details below. We may ask you to verify your identity before
          acting on a request. We retain information for as long as needed to provide the service
          and then delete or de-identify it when no longer needed, unless a longer retention
          period is required for legal, security, dispute-resolution, or backup purposes.
        </p>
        <p>
          Google processes information it receives under
          {' '}<a href="https://policies.google.com/privacy" rel="noreferrer" target="_blank">Google’s Privacy Policy</a>.
          This policy describes Basarat’s handling of information after it is shared with us.
        </p>
      </section>

      <section id="changes">
        <span className="article-index">06 / POLICY UPDATES</span>
        <h2>Changes to this policy</h2>
        <p>
          We may update this policy when our practices or legal requirements change. We will post
          the revised policy on this page and update the “Last updated” date. Please review this
          page periodically for the current policy.
        </p>
      </section>

      <section id="contact">
        <span className="article-index">07 / CONTACT</span>
        <h2>Privacy questions or data requests</h2>
        <p>
          For questions about this policy, Google sign-in data, or to request access to, correction
          of, or deletion of your account information, contact the Basarat privacy team at
          {' '}<a href={`mailto:${contactEmail}`}>{contactEmail}</a>. Include enough information for us
          to understand and verify your request, but do not send your password or Google sign-in
          token.
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
