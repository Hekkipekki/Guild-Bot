input_file = r"C:\Dev Projects\Bot\Guild Bot - Dev\github.txt"

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

total_lines = len(lines)
chunk_size = total_lines // 4

for i in range(4):
    start = i * chunk_size
    end = (i + 1) * chunk_size if i < 3 else total_lines

    output_file = rf"C:\Dev Projects\Bot\Guild Bot - Dev\github_part_{i+1}.txt"

    with open(output_file, "w", encoding="utf-8") as out:
        out.writelines(lines[start:end])

print("File split into 4 parts successfully.")