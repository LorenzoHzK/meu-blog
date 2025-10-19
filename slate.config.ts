/*
 * @file Theme configuration
 */
import { defineConfig } from './src/helpers/config-helper';

export default defineConfig({
  lang: 'en-US',
  site: 'https://lorenzohzk.github.io/meu-blog',
  avatar: '/meu-blog/avatar.jpeg',
  title: 'Matheus Lorenzo Siqueira',
  description:
    'Atualmente trabalho como Front-end, me formei no ensino médio técnico em DS, e atualmente estou cursando TSI-UTFPR',
  lastModified: true,
  readTime: true,
  footer: {
    copyright: '© 2025 Slate Design',
  },
  socialLinks: [
    {
      icon: 'github',
      link: 'https://github.com/lorenzohzk',
    },
  ],
});
