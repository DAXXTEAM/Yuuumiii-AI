module.exports = {
  apps: [
    {
      name: 'Yuuumiii-AI',
      script: 'main.py',
      interpreter: 'python3',
      cwd: '/root/Yuuumiii-AI',
      max_memory_restart: '512M'
    },
    {
      name: 'yuuumiii-bot',
      script: 'telegram_bot.py',
      interpreter: 'python3',
      cwd: '/root/Yuuumiii-AI',
      restart_delay: 5000,
      max_memory_restart: '256M'
    }
  ]
}
