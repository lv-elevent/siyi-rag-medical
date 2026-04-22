from chromadb import PersistentClient

# 👉 和你项目里保持一致
CHROMA_PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "rag_docs"


def main():
    client = PersistentClient(path=CHROMA_PERSIST_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    # 查询所有数据
    results = collection.get(include=["documents", "metadatas"])

    total = len(results["ids"])
    print(f"✅ Chroma 数据库中总数据量：{total} 条")

    if total == 0:
        print("\n❌ 没有找到任何数据，说明分块没有写入 Chroma")
        return

    print("\n📦 示例数据（前3条）：")

    for i in range(total - 3, total):
        print(f"\n--- 第 {i+1} 条 ---")
        print("ID:", results["ids"][i])
        print("文本:", results["documents"][i][:100])
        print("Metadata:", results["metadatas"][i])


if __name__ == "__main__":
    main()