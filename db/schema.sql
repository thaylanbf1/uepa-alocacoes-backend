-- Modelagem Física para o banco de dados principal (MySQL)
-- Engine: InnoDB (para suporte a transações e chaves estrangeiras)
-- Charset: utf8mb4 (para suporte completo a unicode)


SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;


-- -------------------------------------------------------
-- Tabela: tipos_sala
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS tipos_sala (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL
) ENGINE = InnoDB;


-- -------------------------------------------------------
-- Tabela: usuarios
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    tipo_usuario INT COMMENT '1=aluno, 2=instrutor, 3=admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL
) ENGINE = InnoDB;


-- -------------------------------------------------------
-- Tabela: salas
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS salas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sala_ativada BOOLEAN DEFAULT TRUE,
    codigo_sala INT UNIQUE,
    fk_tipo_sala INT,
    ativada BOOLEAN DEFAULT TRUE,
    limite_usuarios INT DEFAULT 0,
    descricao_sala VARCHAR(255),
    imagem VARCHAR(255),
    
    CONSTRAINT fk_sala_tipo FOREIGN KEY (fk_tipo_sala)
        REFERENCES tipos_sala(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE = InnoDB;


-- -------------------------------------------------------
-- Tabela: alocacao
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS alocacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fk_usuario INT NOT NULL,
    fk_sala INT NOT NULL,
    tipo VARCHAR(50) NOT NULL COMMENT 'Ex: aula, evento',
    dia_horario_inicio DATETIME NOT NULL,
    dia_horario_saida DATETIME NOT NULL,
    uso VARCHAR(255) COMMENT 'Ex: Aula de Cálculo I ou Evento de IA',
    justificativa VARCHAR(255),
    oficio VARCHAR(255),
    recurrency TEXT,


    CONSTRAINT fk_aloc_usuario FOREIGN KEY (fk_usuario)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,


    CONSTRAINT fk_aloc_sala FOREIGN KEY (fk_sala)
        REFERENCES salas(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE = InnoDB;
