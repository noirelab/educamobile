export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: ['Inter', 'system-ui', 'sans-serif'],
  			mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
  		},
  		fontSize: {
  			display: ['28px', { lineHeight: '34px', fontWeight: '700' }],
  			title: ['24px', { lineHeight: '32px', fontWeight: '600' }],
  			section: ['17px', { lineHeight: '24px', fontWeight: '600' }],
  			body: ['15px', { lineHeight: '22px', fontWeight: '400' }],
  			label: ['13px', { lineHeight: '18px', fontWeight: '500' }],
  			caption: ['12px', { lineHeight: '16px', fontWeight: '400' }],
  			button: ['15px', { lineHeight: '20px', fontWeight: '600' }],
  			mono: ['13px', { lineHeight: '18px', fontWeight: '400' }]
  		},
  		boxShadow: {
  			glass: 'var(--shadow-glass)',
  			focus: 'var(--focus-ring)'
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'var(--primary)',
  				foreground: 'var(--primary-foreground)'
  			},
  			ink: {
  				DEFAULT: 'var(--ink)',
  				muted: 'var(--ink-muted)'
  			},
  			line: 'var(--line)',
  			glass: {
  				DEFAULT: 'var(--glass)',
  				dense: 'var(--glass-dense)',
  				strong: 'var(--glass-strong)'
  			},
  			'on-sidebar': 'var(--on-sidebar)',
  			'warning-text': 'var(--warning-text)',
  			'success-text': 'var(--success-text)',
  			heat: {
  				low: 'var(--heat-low)',
  				high: 'var(--heat-high)'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'var(--accent)',
  				foreground: 'var(--accent-foreground)',
  				hover: 'var(--accent-hover)',
  				soft: 'var(--accent-soft)'
  			},
  			destructive: {
  				DEFAULT: 'var(--destructive)',
  				foreground: 'var(--destructive-foreground)'
  			},
  			danger: 'var(--danger)',
  			border: 'hsl(var(--border))',
  			warning: 'var(--warning)',
  			success: 'var(--success)',
  			input: 'hsl(var(--input))',
  			ring: 'var(--ring)',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			}
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}
