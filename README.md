# vk-yoink

Configurable script to download images from VK bookmarks, user and group walls, and dialogs\chat rooms.

* Downloads images from different sources in different folders
* Uses upload date as an image name
* Has a progress bar and logging
* Can be gracefully shut down with `ctrl+C`
* Asynchronous

## Install

At least Python 3.7 required.

Install dependencies with:

```pip instal -r requirements.txt```

## Usage

You will need a VK API Token
You can get it [here](https://vkhost.github.io/)
I recommend reading about [them tokens](https://dev.vk.com/api/access-token/implicit-flow-user).
Create a file named `.env` alongside main script `main.py`.
In `.env` add following line:

```TOKEN=your_token_you_got_from_link_above```

Run `python main.py`, specifying where to donload from with parameters below

### Parameters

Flag 	| Desciption
---------------------------|------------
`--fave`	| If set, images will be downloaded from current user bookmarks
`--wall`	| List of wall identificators to download from. For example `--wall id0 club420 fenekc`
`--chat`	| List of chat identificators to download from. For example `--chat c1 12312 -1 c5`
`--path`  | Specify path to download images to. By default downloads to `./data` folder 
`--count` | Specify batch size - how many images to request from vk, and consequently, how many images to download at once

### Example usage

```python main.py --wall haalonean --fave --chat c50 c51```
