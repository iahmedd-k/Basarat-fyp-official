import { useState } from 'react'
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from '@clerk/clerk-react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <header className="flex justify-between items-center p-4 border-b">
        <h1 className="text-xl font-bold">Basarat</h1>
        <nav className="flex items-center gap-4">
          <SignedOut>
            <SignInButton mode="modal" />
            <SignUpButton mode="modal" />
          </SignedOut>
          <SignedIn>
            <UserButton />
          </SignedIn>
        </nav>
      </header>

      <main className="flex-1">
        <section id="center" className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="hero">
            <img src={heroImg} className="base" width="170" height="179" alt="" />
            <img src={reactLogo} className="framework" alt="React logo" />
            <img src={viteLogo} className="vite" alt="Vite logo" />
          </div>
          <div className="text-center mt-8">
            <h1 className="text-4xl font-bold mb-4">Get started</h1>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              Edit <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">src/App.jsx</code> and save to test <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">HMR</code>
            </p>
          </div>
          <button
            type="button"
            className="counter mt-8 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            onClick={() => setCount((count) => count + 1)}
          >
            Count is {count}
          </button>
        </section>

        <div className="ticks"></div>

        <section id="next-steps" className="p-8">
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div id="docs">
              <svg className="icon w-10 h-10 text-blue-600 mb-4" role="presentation" aria-hidden="true">
                <use href="/icons.svg#documentation-icon"></use>
              </svg>
              <h2 className="text-2xl font-bold mb-2">Documentation</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-4">Your questions, answered</p>
              <ul className="space-y-2">
                <li>
                  <a href="https://vite.dev/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline">
                    <img className="logo w-5 h-5" src={viteLogo} alt="" />
                    Explore Vite
                  </a>
                </li>
                <li>
                  <a href="https://react.dev/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline">
                    <img className="button-icon w-5 h-5" src={reactLogo} alt="" />
                    Learn more
                  </a>
                </li>
              </ul>
            </div>
            <div id="social">
              <svg className="icon w-10 h-10 text-green-600 mb-4" role="presentation" aria-hidden="true">
                <use href="/icons.svg#social-icon"></use>
              </svg>
              <h2 className="text-2xl font-bold mb-2">Connect with us</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-4">Join the Vite community</p>
              <ul className="flex flex-wrap gap-4">
                <li>
                  <a href="https://github.com/vitejs/vite" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600">
                    <svg className="button-icon w-5 h-5" role="presentation" aria-hidden="true">
                      <use href="/icons.svg#github-icon"></use>
                    </svg>
                    GitHub
                  </a>
                </li>
                <li>
                  <a href="https://chat.vite.dev/" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600">
                    <svg className="button-icon w-5 h-5" role="presentation" aria-hidden="true">
                      <use href="/icons.svg#discord-icon"></use>
                    </svg>
                    Discord
                  </a>
                </li>
                <li>
                  <a href="https://x.com/vite_js" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600">
                    <svg className="button-icon w-5 h-5" role="presentation" aria-hidden="true">
                      <use href="/icons.svg#x-icon"></use>
                    </svg>
                    X.com
                  </a>
                </li>
                <li>
                  <a href="https://bsky.app/profile/vite.dev" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-blue-600">
                    <svg className="button-icon w-5 h-5" role="presentation" aria-hidden="true">
                      <use href="/icons.svg#bluesky-icon"></use>
                    </svg>
                    Bluesky
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <div className="ticks"></div>
        <section id="spacer" className="h-16"></section>
      </main>
    </>
  )
}

export default App
