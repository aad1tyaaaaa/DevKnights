'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { type MotionValue, motion, useScroll, useTransform } from 'framer-motion'
import { GitHubMark, signInHref, useGitHubAuth, useSignInError } from '@/components/github-auth'

const VIDEO = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/'
const HERO_VIDEO = `${VIDEO}hf_20260622_083515_290e5a10-0b95-41af-a5e2-32b6389baa4d.mp4`
const STORY_VIDEO = `${VIDEO}hf_20260622_092455_089c54f8-3b03-4966-9df1-e9746063d0ef.mp4`
const METRICS_VIDEO = `${VIDEO}hf_20260622_095810_ecea3dd2-fc5e-4e41-8696-4219290b6589.mp4`
const TECH_VIDEO = `${VIDEO}hf_20260622_095750_32a52ce0-2005-45c9-9093-41f03fde9530.mp4`
const FOOTER_VIDEO = `${VIDEO}hf_20260622_080203_fd7f4f85-3a86-4837-8192-85e7bfe68e75.mp4`

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><'
const rand = () => CHARS[Math.floor(Math.random() * CHARS.length)]
const EASE = [0.215, 0.61, 0.355, 1] as const

function ScrambleIn({ text, delay, triggered }: { text: string; delay: number; triggered: boolean }) {
  const [out, setOut] = useState('')
  useEffect(() => {
    if (!triggered) return
    let id: ReturnType<typeof setInterval>
    const t = setTimeout(() => {
      let pos = 0
      id = setInterval(() => {
        pos += 0.5
        const r = Math.floor(pos)
        if (r >= text.length) {
          clearInterval(id)
          setOut(text)
          return
        }
        setOut([...text].map((c, i) => (c === ' ' ? ' ' : i < r ? c : i < r + 3 ? rand() : '')).join(''))
      }, 25)
    }, delay)
    return () => {
      clearTimeout(t)
      clearInterval(id)
    }
  }, [text, delay, triggered])
  return <>{out || ' '}</>
}

function ScrambleText({ text, isHovered, className }: { text: string; isHovered: boolean; className?: string }) {
  const [out, setOut] = useState(text)
  useEffect(() => {
    if (!isHovered) return setOut(text)
    let frame = 0
    const id = setInterval(() => {
      const r = Math.floor(++frame / 4)
      setOut([...text].map((c, i) => (c === ' ' ? ' ' : i < r ? c : rand())).join(''))
      if (r >= text.length) clearInterval(id)
    }, 25)
    return () => clearInterval(id)
  }, [isHovered, text])
  return <span className={className}>{out}</span>
}

function Hover({ children }: { children: (hovered: boolean) => React.ReactNode }) {
  const [h, setH] = useState(false)
  return <span onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)} className="contents">{children(h)}</span>
}

function SquashHamburger({ open, mobile }: { open: boolean; mobile?: boolean }) {
  const [w, h, bar] = mobile ? [15, 10, 1.2] : [18, 12, 1.5]
  const mid = h / 2 - bar / 2
  const spring = { type: 'spring', stiffness: 300, damping: 20 } as const
  const base = { position: 'absolute', left: 0, width: w, height: bar, background: '#fff', borderRadius: bar } as const
  return (
    <span className="relative block" style={{ width: w, height: h }} aria-hidden>
      <motion.span style={{ ...base, top: 0 }} animate={open ? { y: mid, rotate: 45 } : { y: 0, rotate: 0 }} transition={spring} />
      <motion.span style={{ ...base, top: mid }} animate={open ? { opacity: 0, scaleX: 0 } : { opacity: 1, scaleX: 1 }} transition={spring} />
      <motion.span style={{ ...base, top: h - bar }} animate={open ? { y: -mid, rotate: -45 } : { y: 0, rotate: 0 }} transition={spring} />
    </span>
  )
}

const LINKS = [
  { label: 'How it works', id: 'how' },
  { label: 'Metrics', id: 'metrics' },
]

function Navbar({ visible }: { visible: boolean }) {
  const [open, setOpen] = useState(false)
  const spring = { type: 'spring', stiffness: 350, damping: 28 } as const
  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
    setOpen(false)
  }
  const links = (size: string) =>
    LINKS.map(({ label, id }, i) => (
      <Hover key={label}>
        {(h) => (
          <motion.button
            initial={{ opacity: 0, x: 15 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 + i * 0.05 }}
            onClick={() => go(id)}
            className={`${size} whitespace-nowrap font-normal text-white/85 hover:text-white`}
          >
            <ScrambleText text={label} isHovered={h} />
          </motion.button>
        )}
      </Hover>
    ))
  const logo = <img src="/logo.png" alt="" aria-hidden className="size-full object-contain" />
  const { status } = useGitHubAuth()
  const [signInError] = useSignInError()
  const signedIn = status?.connected === true
  // The primary button is always "Sign in with GitHub" until the user is signed in. If the backend has no
  // GitHub OAuth app yet, it opens the sign-in page, which explains the setup instead of erroring.
  const signIn = !signedIn
  const signInTarget = status?.configured ? signInHref('/dashboard') : '/signin'
  const avatar = (size: string) =>
    signedIn && (
      <Link href="/dashboard" title={`Signed in as ${status.login}`} className="block shrink-0 overflow-hidden rounded-full ring-2 ring-white/30 transition hover:ring-white/60">
        {status.avatar_url ? (
          <img src={status.avatar_url} alt={status.login ?? 'GitHub account'} className={size} />
        ) : (
          <span className={`grid place-items-center bg-brand/70 ${size}`}>
            <GitHubMark className="size-5 text-white" />
          </span>
        )}
      </Link>
    )

  const cta = (cls: string, label: { signIn: string; open: string }) => (
    <Hover>
      {(h) => (
        <motion.span whileHover={{ scale: 1.03, backgroundColor: '#6b1239' }} whileTap={{ scale: 0.97 }} className="rounded-full bg-brand">
          {signIn ? (
            <a href={signInTarget} className={`flex items-center gap-2 font-medium text-white ${cls}`}>
              <GitHubMark className="size-[18px]" />
              <ScrambleText text={label.signIn} isHovered={h} />
            </a>
          ) : (
            <Link href="/dashboard" className={`flex items-center gap-2 font-medium text-white ${cls}`}>
              <ScrambleText text={label.open} isHovered={h} />
              <ArrowRight size={15} aria-hidden />
            </Link>
          )}
        </motion.span>
      )}
    </Hover>
  )

  return (
    <motion.header
      initial={{ opacity: 0 }}
      animate={{ opacity: visible ? 1 : 0 }}
      transition={{ duration: 0.8 }}
      className="absolute inset-x-0 top-0 z-50 flex h-20 items-center px-4 sm:px-6 md:px-8"
    >
      {/* Desktop */}
      <div className="hidden w-full items-center justify-between sm:flex">
        <div className="flex items-center gap-2">
          <motion.a
            href="#top"
            aria-label="Provenyx home"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.97 }}
            className={`${open ? 'hidden md:flex' : 'flex'} size-20 shrink-0`}
          >
            {logo}
          </motion.a>
          <motion.nav
            aria-label="Primary"
            animate={{ width: open ? 330 : 48 }}
            transition={spring}
            className="flex h-12 items-center gap-6 overflow-hidden rounded-[14px] bg-brand/70 backdrop-blur-md"
          >
            <button
              onClick={() => setOpen(!open)}
              aria-label={open ? 'Close menu' : 'Open menu'}
              aria-expanded={open}
              className={`grid shrink-0 place-items-center transition-all ${open ? 'ml-1.5 size-9 rounded-[11px] bg-white/10 hover:bg-white/20' : 'size-12 rounded-[14px]'}`}
            >
              <SquashHamburger open={open} />
            </button>
            {open && links('text-[16px]')}
          </motion.nav>
        </div>
        <div className="flex items-center gap-2">
          {signInError && <span role="alert" className="mr-2 rounded-full bg-black/60 px-3 py-1 text-xs text-[#ffb3a8] backdrop-blur">{signInError}</span>}
          {avatar('size-12')}
          {cta('h-12 px-6 text-[15px]', { signIn: 'Sign in with GitHub', open: 'Open dashboard' })}
        </div>
      </div>

      {/* Mobile */}
      <div className="flex w-full items-center gap-2 sm:hidden">
        <motion.a
          href="#top"
          aria-label="Provenyx home"
          animate={{ width: open ? 0 : 56, opacity: open ? 0 : 1 }}
          transition={spring}
          className="flex h-14 shrink-0 overflow-hidden"
        >
          {logo}
        </motion.a>
        <motion.nav
          aria-label="Primary"
          animate={{ width: open ? '100%' : 36 }}
          transition={spring}
          className="flex h-9 items-center gap-4 overflow-hidden rounded-[10px] bg-brand/70 backdrop-blur-md"
        >
          <button onClick={() => setOpen(!open)} aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} className="grid size-9 shrink-0 place-items-center">
            <SquashHamburger open={open} mobile />
          </button>
          {open && links('text-[13px]')}
        </motion.nav>
        <span className="ml-auto flex items-center gap-2">
          {!open && avatar('size-9')}
          {cta('h-9 px-3.5 text-[13px]', { signIn: 'Sign in', open: 'Dashboard' })}
        </span>
      </div>
    </motion.header>
  )
}

const MARQUEE = ['Trust every dependency', 'Verify every release', 'Zero installs', 'Explainable rules', 'Blockchain-anchored records', 'npm lockfile scanning']

function Marquee({ reverse = false }: { reverse?: boolean }) {
  const items = [...MARQUEE, ...MARQUEE]
  return (
    <div aria-hidden className="relative z-20 overflow-hidden border-y border-[#6b1239] bg-brand py-4">
      <div className={`flex w-max ${reverse ? 'animate-marquee-reverse' : 'animate-marquee'}`}>
        {[0, 1].map((copy) => (
          <div key={copy} className="flex shrink-0">
            {items.map((t, i) => (
              <span key={i} className="flex items-center gap-8 pr-8 text-[13px] uppercase tracking-[0.2em] text-white/80 sm:text-[15px]">
                {t}
                <span className="text-[#a8325f]">✦</span>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function BgVideo({ src }: { src: string }) {
  return (
    <>
      <video src={src} autoPlay muted loop playsInline aria-hidden className="absolute inset-0 size-full object-cover" />
      <BrandTint />
    </>
  )
}

function BrandTint() {
  return <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-t from-brand/70 via-black/20 to-black/40" />
}

function Hero({ ready }: { ready: boolean }) {
  const ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const v = ref.current
    if (!v) return
    let lastX: number | null = null
    let target = 0
    let seeking = false
    const seek = () => {
      seeking = true
      v.currentTime = target
    }
    const onSeeked = () => {
      seeking = false
      if (Math.abs(v.currentTime - target) > 0.01) seek()
    }
    const onMove = (e: MouseEvent) => {
      if (lastX !== null && v.duration) {
        target = Math.min(v.duration, Math.max(0, target + ((e.clientX - lastX) / window.innerWidth) * v.duration * 0.8))
        if (!seeking) seek()
      }
      lastX = e.clientX
    }
    v.addEventListener('seeked', onSeeked)
    window.addEventListener('mousemove', onMove)
    return () => {
      v.removeEventListener('seeked', onSeeked)
      window.removeEventListener('mousemove', onMove)
    }
  }, [])

  const h1 = 'font-light leading-[0.95] tracking-[-0.03em] text-white text-[clamp(40px,10vw,100px)]'
  return (
    <section id="top" className="relative h-screen h-[100dvh] overflow-hidden">
      <video ref={ref} src={HERO_VIDEO} muted playsInline preload="auto" aria-hidden className="absolute inset-0 size-full object-cover" />
      <BrandTint />
      <div className="pointer-events-none absolute inset-0 opacity-5" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '24px 24px' }} />
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: ready ? 1 : 0 }} transition={{ duration: 1 }} className="relative flex h-full flex-col px-4 pb-8 pt-20 sm:px-6 sm:pb-12 sm:pt-24 md:px-8">
        <span
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 translate-y-[calc(-50%+50px)] select-none whitespace-nowrap font-bold uppercase leading-none tracking-[-4px] opacity-10"
          style={{
            fontSize: 'clamp(120px, 30vw, 521px)',
            background: 'radial-gradient(circle, rgba(168,50,95,0) 0%, #a8325f 70%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          Provenance
        </span>
        <div className="flex-1" />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-4">
            <h1 className={h1}>
              <ScrambleIn text="Trust Every" delay={200} triggered={ready} />
              <br />
              <ScrambleIn text="Dependency" delay={500} triggered={ready} />
            </h1>
            <motion.p
              initial={{ opacity: 0, y: 25 }}
              animate={ready ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.9, ease: EASE, delay: 0.2 }}
              className="max-w-sm text-[13px] leading-relaxed text-white/60 sm:text-[15px]"
            >
              Provenyx brings software supply-chain investigation into your editor — analyzing your npm lockfile without installing or executing a
              single package.
            </motion.p>
          </div>
          <p className={`${h1} text-left md:text-right`} aria-label="Verify Every Release">
            <ScrambleIn text="Verify Every" delay={700} triggered={ready} />
            <br />
            <ScrambleIn text="Release" delay={1000} triggered={ready} />
          </p>
        </div>
      </motion.div>
    </section>
  )
}

const STORY =
  'Provenyx follows every package in your lockfile, direct and transitive, without running a line of it. Explainable rules over public npm ' +
  'metadata surface unusual releases. Blockchain-anchored manifest hashes show whether a release record matches what was published. Every ' +
  'finding shows its reasoning.'

/** One word that brightens from dim to full white as scrolling reaches its share of the paragraph. */
function ScrollWord({ word, progress, range }: { word: string; progress: MotionValue<number>; range: [number, number] }) {
  const opacity = useTransform(progress, range, [0.2, 1])
  return <motion.span style={{ opacity }}>{word} </motion.span>
}

function Story() {
  const ref = useRef<HTMLParagraphElement>(null)
  // 0 when the paragraph's top enters the bottom of the screen, 1 when its bottom reaches the middle.
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.5'] })
  const words = STORY.split(' ')
  return (
    <section id="how" className="relative flex h-screen h-[100dvh] items-center justify-center overflow-hidden">
      <BgVideo src={STORY_VIDEO} />
      <div className="absolute inset-x-0 top-0 z-10 h-[180px]" style={{ background: 'linear-gradient(#010103, transparent)' }} />
      <div className="relative z-10 mx-auto max-w-5xl">
        <p
          ref={ref}
          aria-label={STORY}
          className="px-6 text-center font-sans text-[22px] font-normal leading-[1.35] tracking-[-0.02em] text-white sm:px-12 sm:text-[30px] md:text-[36px] lg:text-[42px]"
        >
          {words.map((word, i) => (
            <ScrollWord key={i} word={word} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} />
          ))}
        </p>
      </div>
    </section>
  )
}

const METRICS = [
  { value: '0', label: 'Packages installed or executed' },
  { value: '100%', label: 'Transitive dependencies mapped' },
  { value: '3', label: 'Independent evidence layers' },
]

function Metrics() {
  return (
    <section id="metrics" className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-32">
      <BgVideo src={METRICS_VIDEO} />
      <div className="relative mx-auto w-full max-w-6xl">
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 1.2 }}
          className="mb-20 text-center text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]"
        >
          Safe by design
        </motion.p>
        <div className="grid gap-16 text-center md:grid-cols-3 md:gap-8">
          {METRICS.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.8, delay: i * 0.15 }}
            >
              <p className="text-[clamp(48px,10vw,96px)] font-light leading-none tracking-[-0.04em] text-white">{m.value}</p>
              <p className="mt-4 text-[13px] tracking-wide text-white/40 sm:text-[15px]">{m.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

const FEATURES = [
  { title: 'Dependency Mapping', body: 'See exactly how every package reaches your project from package-lock.json.' },
  { title: 'Release Anomalies', body: 'Explainable rules flag release behavior worth a closer look.' },
  { title: 'Release Verification', body: 'Compare metadata with blockchain-anchored manifest hashes.' },
  { title: 'Editor Native', body: 'Scan and investigate from the VS Code extension.' },
]

function Technology() {
  const up = (y: number, delay = 0) => ({
    initial: { opacity: 0, y },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.3 },
    transition: { duration: 1, delay },
  })
  return (
    <section className="relative flex h-screen h-[100dvh] flex-col overflow-hidden px-8 py-12 sm:px-12 sm:py-16 md:px-16">
      <BgVideo src={TECH_VIDEO} />
      <div className="relative flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <motion.h2 {...up(40)} className="text-[clamp(36px,8vw,72px)] font-light leading-[0.95] tracking-[-0.03em] text-white">
          Explainable
          <br />
          Detection
        </motion.h2>
        <motion.p {...up(20, 0.2)} className="max-w-xs text-[13px] leading-relaxed text-white/50 sm:text-[15px] md:pt-2 md:text-right">
          Every flag shows the rule that fired and the metadata behind it. No black-box scores — just evidence you can check yourself.
        </motion.p>
      </div>
      <div className="flex-1" />
      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 1, delay: 0.3 }}
        className="relative grid grid-cols-2 gap-8 md:grid-cols-4 md:gap-6"
      >
        {FEATURES.map((f, i) => (
          <motion.div key={f.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.7, delay: i * 0.1 }}>
            <h3 className="mb-2 text-[14px] font-normal text-white sm:text-[16px]">{f.title}</h3>
            <p className="text-[12px] leading-relaxed text-white/40 sm:text-[14px]">{f.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  )
}

const LAYERS = ['Map', 'Detect', 'Verify']

function Architecture() {
  const view = { once: true, amount: 0.4 }
  return (
    <section id="safety" className="flex min-h-screen items-center justify-center px-6 py-32" style={{ background: "radial-gradient(ellipse at center, #460a26 0%, #000 70%)" }}>
      <div className="mx-auto w-full max-w-3xl text-center">
        <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={view} transition={{ duration: 1 }}>
          <p className="mb-8 text-[13px] uppercase tracking-[0.2em] text-white/40 sm:text-[14px]">Architecture</p>
          <h2 className="mb-10 text-[clamp(28px,6vw,56px)] font-light leading-[1.15] tracking-[-0.02em] text-white">Three layers. Zero installs.</h2>
          <p className="mx-auto max-w-xl text-[15px] leading-relaxed text-white/45 sm:text-[17px]">
            Your lockfile is sent only after you confirm each scan. A missing on-chain record is an evidence gap, not proof of compromise — and a
            matching hash confirms a record&apos;s integrity, not that a package is safe.
          </p>
        </motion.div>
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={view} transition={{ duration: 1.2, delay: 0.4 }} className="mt-20 flex flex-col items-center gap-4">
          {LAYERS.map((name, i) => (
            <div key={name} className="flex h-[72px] w-full max-w-md items-center justify-between rounded-lg border border-[#6b1239] bg-black/40 px-6">
              <span className="text-[12px] uppercase tracking-[0.15em] text-white/30">Layer {i + 1}</span>
              <span className="text-[16px] font-light text-white sm:text-[18px]">{name}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="flex min-h-[400px] flex-col overflow-hidden bg-black md:flex-row">
      <div className="relative h-[300px] md:h-auto md:w-1/2">
        <BgVideo src={FOOTER_VIDEO} />
      </div>
      <div className="flex flex-col justify-between bg-brand p-10 sm:p-16 md:w-1/2">
        <div>
          <div className="mb-8 flex items-center gap-2.5">
            <img src="/logo.png" alt="" aria-hidden className="size-8 opacity-70" />
            <span className="text-[15px] font-medium tracking-tight text-white/70">provenyx</span>
          </div>
          <p className="max-w-sm text-[14px] leading-relaxed text-white/40 sm:text-[15px]">
            Trust every dependency. Verify every release. Software supply-chain security for npm projects.
          </p>
        </div>
        <p className="mt-12 text-[12px] text-white/40">© 2026 Provenyx Security · v0.1.0 preview</p>
      </div>
    </footer>
  )
}

export function Landing() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 800)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="dark bg-black text-white">
      <Navbar visible={ready} />
      <main>
        <Hero ready={ready} />
        <Marquee />
        <Story />
        <Marquee reverse />
        <Metrics />
        <Marquee />
        <Technology />
        <Marquee reverse />
        <Architecture />
      </main>
      <Marquee />
      <Footer />
    </div>
  )
}
