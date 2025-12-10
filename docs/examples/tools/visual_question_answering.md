# Visual question answering (VQA)

This simple agent network consists of a frontman agent and a "tool" agent,
i.e. an agent that calls Python code. The agent network allows for:

* Posing a query about an image or a video file
* Calling a coded tool (a Python function) to answer the query using Apple's ml-fastvlm library
* Using `sly_data` to pass in the location of the image or video file
* Returning the answer to the query in json format

## Prerequisite: Set up Visual Question Answering (VQA)

1. Clone `ml-fastvlm` repository in the same folder as `neuro-san-studio`. E.g., both `neuro-san-studio` and
`ml-fastvlm` are cloned in `~/MyProjects` folder.

```bash
git clone https://github.com/kxk302/ml-fastvlm.git
```

2. Change the directory to `ml-fastvlm`

```bash
cd ml-fastvlm
```

3. Using Python *3.10*, create/activate a virtual environment

```bash
python3 -m venv venv;
. ./venv/bin/activate
```

4. Install `ml-fastvlm` repo

```bash
pip install -e .
```

5. Install opencv

```bash
pip install opencv-python==4.8.0.74
```

6. To download all the pretrained checkpoints, run the command below (note that this might take some
time depending on your connection so might be good to grab ☕️ while you wait). Files will be downloaded
to the `checkpoints` directory.

```bash
bash get_models.sh
```

## File

[visual_question_answering.hocon](../../../registries/tools/visual_question_answering.hocon)

## Description

Visual question answering (VQA) is an agent network that can answer questions about image and video files.
It calls a coded tool that uses Apple's ml-fastvlm library to answer the query. The agent network uses the
`sly_data` to pass in the location of the image or video file. The answer to the query is returned in json format.

## Example conversation

Image question: specify the location of an image file in `sly_data`. The image contains a number of people.

```json
{
    "file_path":"/tmp/image.jpg"
}
```

```text
Human: How many people are in the image?
AI: { "answer": "There are 14 people in the image." }
```

Expectation: the answer should say the number of people in the image.

Video question: specify the location of a video file in `sly_data`. The video contains an animal.

```json
{
    "file_path":"/tmp/video.mp4"
}
```

```text
Human: What animal is in the video?
AI: { "answer": "The animal in the video is an ostrich" }
```

Expectation: the answer should say the animal in the video.
