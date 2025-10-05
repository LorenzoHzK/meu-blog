/*
 * @file Theme configuration
 */
import { defineConfig } from './src/helpers/config-helper';

export default defineConfig({
  lang: 'en-US',
  site: 'https://lorenzohzk.github.io/meu-blog',
  avatar: '/meu-blog/avatar.jpeg',
  title: 'Meu blog',
  description: 'Neste blog pretendo colocar algumas informações, e também colocar algumas coisas que eu estou estudando ao longo da minha jornada',
  lastModified: true,
  readTime: true,
  footer: {
    copyright: '© 2025 Slate Design',
  },
  socialLinks: [
    {
      icon: 'github',
      link: 'https://github.com/lorenzohzk'
    },
]
});