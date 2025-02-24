from asyncio import sleep

from twitchbot import Mod, channels, add_balance, session, cfg, task_running, add_task, stop_task


class LoyaltyTicketMod(Mod):
    name = "LoyaltyTicketMod"
    LOYALTY_TICKER_TASK_NAME = "LoyaltyTicketModTask"

    async def loaded(self):
        if cfg.loyalty_interval == -1:
            print('loyalty_interval in config is -1, loyalty ticker WILL NOT start')
            return

        if not task_running(self.LOYALTY_TICKER_TASK_NAME):
            add_task(self.LOYALTY_TICKER_TASK_NAME, self._ticker_loop())

    async def unloaded(self):
        stop_task(self.LOYALTY_TICKER_TASK_NAME)

    async def _ticker_loop(self):
        print(f'loyalty ticker started!')
        while True:
            for channel in channels.values():
                for viewer in channel.chatters.all_viewers:
                    add_balance(channel.name, viewer, cfg.loyalty_amount, commit=False)
                    await sleep(.2)
                session.commit()

            await sleep(cfg.loyalty_interval)
