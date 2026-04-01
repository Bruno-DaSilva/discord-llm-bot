import discord


class DeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.grey, emoji="\N{WASTEBASKET}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()


class DeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DeleteButton())
