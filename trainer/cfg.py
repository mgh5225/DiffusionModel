import os
import utils
from models.unet_conditional import ConditionalUNet
from models.cfg_diffusion import CFGDiffusion
import torch
from torch import optim, nn
from torch.utils.tensorboard.writer import SummaryWriter
import numpy as np
import logging


logging.basicConfig(
    format="%(asctime)s - %(levelname)s: %(message)s",
    level=logging.INFO,
    datefmt="%I:%M:%S",
)


def train(args: dict):
    utils.setup_logging(args.run_name)
    device = args.device

    dataloader = utils.create_dataset(args)

    model = ConditionalUNet(
        in_channels=args.in_channels,
        out_channels=args.in_channels,
        time_dim=args.time_dim,
        num_classes=args.num_classes,
    ).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr)
    mse = nn.MSELoss()

    diffusion = CFGDiffusion(
        T=args.T,
        beta_start=args.beta_start,
        beta_end=args.beta_end,
        img_size=args.img_size,
        in_channels=args.in_channels,
        device=device,
    )

    logger = SummaryWriter(os.path.join("runs", args.run_name))

    len_data = len(dataloader)

    for epoch in range(args.epochs):
        logging.info(f"Starting epoch {epoch}")

        for i, (images, labels) in enumerate(dataloader):
            images = images.to(device)
            labels = labels.to(device)

            t = diffusion.t(images.shape[0])

            x_t, noise = diffusion.forward(images, t)

            if np.random.random() < args.alpha:
                labels = None

            noise_pred = model(x_t, t, labels)

            loss = mse(noise, noise_pred)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            logger.add_scalar("MSE", loss.item(), global_step=epoch * len_data + i)

        labels = torch.arange(args.num_classes).long().to(device)
        sampled_images = diffusion.sample(
            model,
            n=images.shape[0],
            labels=labels,
            cfg_scale=args.cfg_scale,
        )
        utils.save_images(
            sampled_images, os.path.join("results", args.run_name, f"{epoch}.jpg")
        )
        torch.save(
            model.state_dict(),
            os.path.join("models", args.run_name, f"ckpt-{epoch}.pt"),
        )


def lunch():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--run_name", type=str, default="CFG")
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--batch_size", type=int, default=12)
    parser.add_argument("--shuffle", type=bool, default=True)
    parser.add_argument("--img_size", type=int, default=64)
    parser.add_argument("--in_channels", type=int, default=3)
    parser.add_argument("--T", type=int, default=1000)
    parser.add_argument("--beta_start", type=float, default=1e-4)
    parser.add_argument("--beta_end", type=float, default=2e-2)
    parser.add_argument("--time_dim", type=int, default=256)
    parser.add_argument("--dataset_path", type=str, required=True)
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--num_classes", type=int, required=True)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--cfg_scale", type=float, default=0.1)

    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    lunch()
